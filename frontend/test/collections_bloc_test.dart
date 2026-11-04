import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/collections/data/models/collections_model.dart';
import 'package:shgad/features/collections/domain/entities/collections.dart';
import 'package:shgad/features/collections/domain/repositories/collections_repository.dart';
import 'package:shgad/features/collections/domain/usecases/collections_usecases.dart';
import 'package:shgad/features/collections/presentation/bloc/draft_bloc.dart';
import 'collections_model_test.dart' show collectionAmount, collectionDraftJson;

class FakeConnection implements ConnectionRepository {
  bool available = true;
  final controller = StreamController<bool>.broadcast();
  @override
  bool get online => available;
  @override
  Stream<bool> get changes => controller.stream;
  @override
  Future<bool> check() async => available;
}

class FakeCollectionsRepository implements CollectionsRepository {
  bool template = false, failDraft = false, failLog = false;
  final actions = <ReminderAction>[];
  @override
  Future<Result<CollectionDraft>> draft(String id, String tone) async =>
      failDraft
      ? const Failed(AppFailure(FailureKind.unavailable))
      : Success(
          CollectionsModel.draft({
            ...collectionDraftJson(template: template),
            'tone': tone,
          }),
        );
  @override
  Future<Result<ReminderReceipt>> log(ReminderAction action) async {
    actions.add(action);
    return failLog
        ? const Failed(AppFailure(FailureKind.offline))
        : Success(
            CollectionsModel.receipt({
              'reminder_id': 1,
              'counterparty_id': action.customerId,
              'channel': action.channel,
              'business_date': '2026-09-28',
              'recorded_at': '2026-11-04T10:00:00Z',
              'overdue_amount': collectionAmount(),
            }),
          );
  }

  @override
  Future<Result<Snapshot<Collections>>> load() async =>
      const Failed(AppFailure(FailureKind.unavailable));
  @override
  Future<Result<Snapshot<MorningBriefData>>> brief() async =>
      const Failed(AppFailure(FailureKind.unavailable));
}

class FakeSharing implements ReminderSharingRepository {
  final texts = <String>[], channels = <String>[];
  bool opened = true;
  @override
  Future<Result<bool>> share(String text, String channel) async {
    texts.add(text);
    channels.add(channel);
    return Success(opened);
  }
}

void main() {
  late FakeCollectionsRepository repo;
  late FakeSharing sharing;
  late FakeConnection connection;
  late DraftBloc bloc;
  setUp(() {
    repo = FakeCollectionsRepository();
    sharing = FakeSharing();
    connection = FakeConnection();
    bloc = DraftBloc(
      MakeReminderDraft(repo),
      ShareReminderText(sharing),
      LogReminder(repo),
      WatchConnectivity(connection),
    );
  });
  tearDown(() async {
    await bloc.close();
    await connection.controller.close();
  });
  Future<void> open() async {
    final ready = bloc.stream.firstWhere(
      (s) => s is DraftLoaded || s is DraftFailure,
    );
    bloc.add(const OpenReminder('CUST-01', 'gentle'));
    await ready;
  }

  test('draft loading then ready, typed failure preserves view', () async {
    final states = <DraftState>[];
    final sub = bloc.stream.listen(states.add);
    await open();
    expect(states.first, isA<DraftLoading>());
    expect(bloc.state, isA<DraftLoaded>());
    repo.failDraft = true;
    await open();
    expect(bloc.state, isA<DraftFailure>());
    expect((bloc.state as DraftFailure).failure, isA<AppFailure>());
    await sub.cancel();
  });

  for (final channel in ['copy', 'whatsapp']) {
    test('merchant $channel uses edited text then logs exact action', () async {
      await open();
      bloc.add(const EditReminder('merchant edited text'));
      await Future<void>.delayed(Duration.zero);
      final saved = bloc.stream.firstWhere((s) => s.view.receipt != null);
      bloc.add(ShareReminder(channel));
      await saved;
      expect(sharing.texts, ['merchant edited text']);
      expect(sharing.channels, [channel]);
      expect(repo.actions.single.edited, isTrue);
      expect(repo.actions.single.customerId, 'CUST-01');
    });
  }

  test('blocked external handoff never logs', () async {
    sharing.opened = false;
    await open();
    final failed = bloc.stream.firstWhere((s) => s is DraftFailure);
    bloc.add(const ShareReminder('whatsapp'));
    await failed;
    expect(repo.actions, isEmpty);
  });

  test('log retry never repeats already completed handoff', () async {
    repo.failLog = true;
    await open();
    final failed = bloc.stream.firstWhere((s) => s is DraftFailure);
    bloc.add(const ShareReminder('copy'));
    await failed;
    expect(bloc.state.view.pending, isNotNull);
    repo.failLog = false;
    final saved = bloc.stream.firstWhere((s) => s.view.receipt != null);
    bloc.add(const RetryReminderLog());
    await saved;
    expect(sharing.texts, hasLength(1));
    expect(repo.actions, hasLength(2));
  });

  test('offline retains text and prevents handoff/log', () async {
    await open();
    bloc.add(const EditReminder('retained draft'));
    await Future<void>.delayed(Duration.zero);
    connection.available = false;
    connection.controller.add(false);
    await bloc.stream.firstWhere((s) => s is DraftOffline);
    bloc.add(const ShareReminder('copy'));
    await Future<void>.delayed(Duration.zero);
    expect(bloc.state.view.text, 'retained draft');
    expect(sharing.texts, isEmpty);
    expect(repo.actions, isEmpty);
  });

  test(
    'pending unapproved template can be viewed but never handed off',
    () async {
      repo.template = true;
      await open();
      bloc.add(const ShareReminder('copy'));
      await Future<void>.delayed(Duration.zero);
      expect(sharing.texts, isEmpty);
      expect(repo.actions, isEmpty);
    },
  );
}
