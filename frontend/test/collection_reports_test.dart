import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/session_events.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/presentation/report_bloc.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/collections/data/models/collections_model.dart';
import 'package:shgad/features/collections/data/repositories/reminder_sharing_impl.dart';
import 'package:shgad/features/collections/domain/entities/collections.dart';
import 'package:shgad/features/collections/domain/usecases/collections_usecases.dart';
import 'package:shgad/features/collections/presentation/bloc/collections_bloc.dart';
import 'package:shgad/features/collections/presentation/bloc/draft_bloc.dart';
import 'collections_bloc_test.dart'
    show FakeCollectionsRepository, FakeConnection, FakeSharing;
import 'collections_model_test.dart' show collectionsJson;

class CachedCollections extends FakeCollectionsRepository {
  @override
  Future<Result<Snapshot<Collections>>> load() async => Success(
    Snapshot(
      CollectionsModel.collections(collectionsJson()),
      '2026-11-04T10:00:00Z',
      offline: true,
    ),
  );
}

void main() {
  blocTest<CollectionsBloc, ReportState<Collections>>(
    'collections cache preserves its last-sync time offline',
    build: () => CollectionsBloc(LoadCollections(CachedCollections())),
    act: (bloc) => bloc.add(const RefreshReport()),
    expect: () => [
      isA<ReportLoading<Collections>>(),
      isA<ReportOffline<Collections>>().having(
        (s) => s.snapshot.updatedAt,
        'last sync',
        '2026-11-04T10:00:00Z',
      ),
    ],
  );
  blocTest<MorningBriefBloc, ReportState<MorningBriefData>>(
    'brief failure stays typed instead of inventing figures',
    build: () =>
        MorningBriefBloc(LoadMorningBrief(FakeCollectionsRepository())),
    act: (bloc) => bloc.add(const RefreshReport()),
    expect: () => [
      isA<ReportLoading<MorningBriefData>>(),
      isA<ReportFailure<MorningBriefData>>(),
    ],
  );
  test('reset clears edited draft and pending handoff state', () async {
    final events = SessionEvents(), connection = FakeConnection();
    final bloc = DraftBloc(
      MakeReminderDraft(FakeCollectionsRepository()),
      ShareReminderText(FakeSharing()),
      LogReminder(FakeCollectionsRepository()),
      WatchConnectivity(connection),
      WatchSessionReset(events),
    );
    final loaded = bloc.stream.firstWhere((s) => s is DraftLoaded);
    bloc.add(const OpenReminder('CUST-01', 'gentle'));
    await loaded;
    bloc.add(const EditReminder('in-memory edit'));
    await Future<void>.delayed(Duration.zero);
    final cleared = bloc.stream.firstWhere((s) => s is DraftInitial);
    events.reset();
    await cleared;
    expect(bloc.state.view.text, isEmpty);
    expect(bloc.state.view.draft, isNull);
    expect(bloc.state.view.pending, isNull);
    await bloc.close();
    await events.dispose();
    await connection.controller.close();
  });
  test('WhatsApp URL contains text only and round-trips Arabic edits', () {
    const text = 'هلا أم نور، & ? #\nتذكير بالمبلغ';
    final uri = ReminderSharingImpl.whatsappUri(text);
    expect(uri.scheme, 'https');
    expect(uri.host, 'wa.me');
    expect(uri.path, '/');
    expect(uri.queryParameters, {'text': text});
  });
}
