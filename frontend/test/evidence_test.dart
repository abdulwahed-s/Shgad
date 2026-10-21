import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/evidence_request.dart';
import 'package:shgad/core/domain/new_client_id.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/evidence/data/datasources/evidence_remote.dart';
import 'package:shgad/features/evidence/data/models/source_model.dart';
import 'package:shgad/features/evidence/data/repositories/evidence_repository_impl.dart';
import 'package:shgad/features/evidence/domain/entities/source_record.dart';
import 'package:shgad/features/evidence/domain/repositories/evidence_repository.dart';
import 'package:shgad/features/evidence/domain/usecases/evidence_usecases.dart';
import 'package:shgad/features/evidence/presentation/bloc/evidence_bloc.dart';
import 'package:shgad/features/quick_entry/domain/usecases/entry_usecases.dart';
import 'entry_test.dart' show FakeConnection, MockEntryRepository;
import 'support/fixtures.dart';

class MockEvidenceRemote extends Mock implements EvidenceRemote {}

class MockEvidenceRepository extends Mock implements EvidenceRepository {}

void main() {
  test(
    'Evidence repository retains voided originals, reference costs and typed failures',
    () async {
      final remote = MockEvidenceRemote();
      final repo = EvidenceRepositoryImpl(remote);
      when(() => remote.load(any())).thenAnswer((_) async => sourcesJson());
      final records =
          (await repo.load(['CNT-090', 'CAT-01'])
                  as Success<List<SourceRecord>>)
              .value;
      expect(records.first.row!.amount.value, 12000);
      expect(records.first.row!.voidReason, 'mistyped');
      expect(records.last.buy!.value, 1000);
      when(() => remote.detail(any())).thenAnswer(
        (_) async => ledgerJson(id: 'CORRECTION', correction: 'CNT-090'),
      );
      expect(
        (await repo.detail('CORRECTION') as Success<LedgerRow>)
            .value
            .correctionOf,
        'CNT-090',
      );
      when(
        () => remote.load(any()),
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      expect(await repo.load(['CNT-090']), isA<Failed>());
    },
  );
  test('Evidence chunks requests and rejects incomplete evidence', () async {
    final remote = MockEvidenceRemote();
    final repo = EvidenceRepositoryImpl(remote);
    when(() => remote.load(any())).thenAnswer(
      (invocation) async => {
        'items': [
          for (final id in invocation.positionalArguments.first as List<String>)
            {
              'kind': 'transaction',
              'source_id': id,
              'transaction': ledgerJson(id: id),
              'category': null,
              'opening_balance': null,
            },
        ],
      },
    );
    final result = await repo.load(List.generate(205, (i) => 'SOURCE-$i'));
    expect((result as Success<List<SourceRecord>>).value.length, 205);
    final calls = verify(
      () => remote.load(captureAny()),
    ).captured.cast<List<String>>();
    expect(calls.map((c) => c.length), [100, 100, 5]);
    when(
      () => remote.load(any()),
    ).thenAnswer((_) async => {'items': <Object>[]});
    expect(await repo.load(['MISSING']), isA<Failed>());
  });
  for (final mode in ['loaded', 'offline', 'failure']) {
    late FakeConnection connection;
    blocTest<EvidenceBloc, EvidenceState>(
      'Evidence loading to $mode',
      build: () {
        connection = FakeConnection();
        final repo = MockEvidenceRepository();
        when(() => repo.load(any())).thenAnswer(
          (_) async => mode == 'loaded'
              ? Success(
                  (sourcesJson()['items'] as List)
                      .map(SourceModel.parse)
                      .toList(),
                )
              : Failed(
                  AppFailure(
                    mode == 'offline'
                        ? FailureKind.offline
                        : FailureKind.notFound,
                  ),
                ),
        );
        return EvidenceBloc(
          LoadEvidence(repo),
          LoadSourceDetail(repo),
          UndoEntry(MockEntryRepository()),
          WatchConnectivity(connection),
          CheckConnectivity(connection),
          NewClientId(),
        );
      },
      act: (b) => b.add(
        const OpenEvidence(
          EvidenceRequest(['CNT-090', 'CAT-01'], 'source formula'),
        ),
      ),
      expect: () => [
        isA<EvidenceLoading>(),
        switch (mode) {
          'loaded' => isA<EvidenceLoaded>(),
          'offline' => isA<EvidenceOffline>(),
          _ => isA<EvidenceFailure>(),
        },
      ],
      tearDown: () => connection.controller.close(),
    );
  }
}
