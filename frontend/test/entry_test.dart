import 'dart:async';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/new_client_id.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/quick_entry/data/datasources/entry_remote.dart';
import 'package:shgad/features/quick_entry/data/repositories/entry_repository_impl.dart';
import 'package:shgad/features/quick_entry/domain/entities/entry.dart';
import 'package:shgad/features/quick_entry/domain/repositories/entry_repository.dart';
import 'package:shgad/features/quick_entry/domain/usecases/entry_usecases.dart';
import 'package:shgad/features/quick_entry/presentation/bloc/entry_bloc.dart';

class MockEntryRemote extends Mock implements EntryRemote {}

class MockEntryRepository extends Mock implements EntryRepository {}

class FakeConnection implements ConnectionRepository {
  bool connected = true;
  final controller = StreamController<bool>.broadcast();
  @override
  bool get online => connected;
  @override
  Stream<bool> get changes => controller.stream;
  @override
  Future<bool> check() async => connected;
  void set(bool value) {
    connected = value;
    controller.add(value);
  }
}

void main() {
  setUpAll(() => registerFallbackValue(const EntryDraft('fallback', {})));
  late MockEntryRepository repo;
  late FakeConnection connection;
  EntryBloc build() => EntryBloc(
    LoadEntrySetup(repo),
    SaveEntry(repo),
    UndoEntry(repo),
    WatchConnectivity(connection),
    CheckConnectivity(connection),
    NewClientId(),
  );
  setUp(() {
    repo = MockEntryRepository();
    connection = FakeConnection();
    when(
      repo.setup,
    ).thenAnswer((_) async => const Success(EntrySetup('2026-09-28', {})));
    when(() => repo.save(any())).thenAnswer(
      (_) async => const Success(SavedEntry('ENT-1', 'TX-1', false)),
    );
    when(() => repo.undo(any(), any(), any())).thenAnswer(
      (_) async => const Success(VoidedEntry('ENT-1', 'VOID-1', 'mistyped')),
    );
  });
  tearDown(() => connection.controller.close());
  test(
    'Repository sends strict integer IQD and exact allowed fields; maps typed error',
    () async {
      final remote = MockEntryRemote();
      final repository = EntryRepositoryImpl(remote);
      when(() => remote.save(any())).thenAnswer(
        (_) async => {
          'source_id': 'ENT-1',
          'transaction_id': 'TX-1',
          'duplicate': false,
        },
      );
      final result = await repository.save(
        const EntryDraft('same-id', {
          'type': 'CASH_SALE',
          'business_date': '2026-09-28',
          'amount_iqd': '١٢٠٠٠',
        }),
      );
      expect(result, isA<Success<SavedEntry>>());
      final body =
          verify(() => remote.save(captureAny())).captured.single as Map;
      expect(body['amount_iqd'], 12000);
      expect(body['client_entry_id'], 'same-id');
      expect(body.keys.toSet(), {
        'client_entry_id',
        'type',
        'business_date',
        'amount_iqd',
        'counterparty_id',
        'obligation_id',
        'due_date',
        'note',
        'correction_of_source_id',
      });
      when(
        () => remote.save(any()),
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      expect(
        await repository.save(const EntryDraft('same-id', {})),
        isA<Failed<SavedEntry>>(),
      );
    },
  );
  blocTest<EntryBloc, EntryState>(
    'Entry confirmation is required before saving',
    build: build,
    act: (bloc) async {
      bloc.add(const OpenEntry({'amount_iqd': '١٢٠٠٠'}));
      await bloc.stream.firstWhere((s) => s is EntryLoaded);
      bloc.add(const ConfirmEntry());
      await Future<void>.delayed(Duration.zero);
      verifyNever(() => repo.save(any()));
      bloc.add(const PrepareEntry());
      await bloc.stream.firstWhere((s) => s.view.mode == EntryMode.confirm);
      bloc.add(const ConfirmEntry());
    },
    expect: () => [
      isA<EntryLoading>(),
      isA<EntryLoaded>(),
      isA<EntryLoaded>().having(
        (s) => s.view.mode,
        'confirm',
        EntryMode.confirm,
      ),
      isA<EntryLoading>(),
      isA<EntryLoaded>().having(
        (s) => s.view.saved?.sourceId,
        'saved source',
        'ENT-1',
      ),
    ],
  );
  blocTest<EntryBloc, EntryState>(
    'T33 offline preserves typed values; no queued save on reconnect',
    build: build,
    act: (bloc) async {
      bloc.add(const OpenEntry({'amount_iqd': '١٢٠٠٠'}));
      await bloc.stream.firstWhere((s) => s is EntryLoaded);
      connection.set(false);
      await bloc.stream.firstWhere((s) => s is EntryOffline);
      bloc.add(const ConfirmEntry());
      bloc.add(const ChangeEntry('note', 'retained note'));
      await Future<void>.delayed(Duration.zero);
      connection.set(true);
    },
    expect: () => [
      isA<EntryLoading>(),
      isA<EntryLoaded>(),
      isA<EntryOffline>(),
      isA<EntryOffline>().having(
        (s) => s.view.draft.amountText,
        'amount',
        '١٢٠٠٠',
      ),
      isA<EntryLoaded>().having(
        (s) => s.view.draft.fields['note'],
        'note',
        'retained note',
      ),
    ],
    verify: (_) => verifyNever(() => repo.save(any())),
  );
  blocTest<EntryBloc, EntryState>(
    'Entry typed failure retains draft',
    build: () {
      when(repo.setup).thenAnswer(
        (_) async => const Failed(AppFailure(FailureKind.validation)),
      );
      return build();
    },
    act: (bloc) => bloc.add(const OpenEntry({'amount_iqd': '١٢٠٠٠'})),
    expect: () => [
      isA<EntryLoading>(),
      isA<EntryFailure>().having(
        (s) => s.view.draft.amountText,
        'retained',
        '١٢٠٠٠',
      ),
    ],
  );
  test('Undo requires merchant reason and retains audit IDs', () async {
    final bloc = build();
    bloc.add(const OpenEntry({'amount_iqd': '12000'}));
    await bloc.stream.firstWhere((s) => s is EntryLoaded);
    bloc.add(const PrepareEntry());
    await bloc.stream.firstWhere((s) => s.view.mode == EntryMode.confirm);
    bloc.add(const ConfirmEntry());
    await bloc.stream.firstWhere((s) => s.view.mode == EntryMode.saved);
    bloc.add(const BeginUndo());
    await bloc.stream.firstWhere((s) => s.view.mode == EntryMode.undo);
    bloc.add(const ChangeUndoReason('mistyped'));
    await Future<void>.delayed(Duration.zero);
    bloc.add(const ConfirmUndo());
    await bloc.stream.firstWhere((s) => s.view.mode == EntryMode.voided);
    expect(bloc.state.view.voided!.voidId, 'VOID-1');
    verify(() => repo.undo('ENT-1', any(), 'mistyped')).called(1);
    await bloc.close();
  });
}
