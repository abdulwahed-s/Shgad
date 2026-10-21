import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/presentation/report_bloc.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/debts/data/datasources/debts_remote.dart';
import 'package:shgad/features/debts/data/models/debts_model.dart';
import 'package:shgad/features/debts/data/repositories/debts_repository_impl.dart';
import 'package:shgad/features/debts/domain/entities/debts.dart';
import 'package:shgad/features/debts/domain/repositories/debts_repository.dart';
import 'package:shgad/features/debts/domain/usecases/load_debts.dart';
import 'package:shgad/features/debts/presentation/bloc/debts_bloc.dart';
import 'core_test.dart' show MemoryCache;
import 'support/fixtures.dart';

class MockDebtsRemote extends Mock implements DebtsRemote {}

class MockDebtsRepository extends Mock implements DebtsRepository {}

void main() {
  test(
    'Debts repository maps real response, caches and retains timestamp offline',
    () async {
      final remote = MockDebtsRemote();
      final repo = DebtsRepositoryImpl(remote, CachedReader(MemoryCache()));
      when(remote.load).thenAnswer((_) async => debtsJson());
      final online = (await repo.load() as Success<Snapshot<Debts>>).value;
      when(
        remote.load,
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      final offline = (await repo.load() as Success<Snapshot<Debts>>).value;
      expect(offline.offline, isTrue);
      expect(offline.updatedAt, online.updatedAt);
      verify(remote.load).called(2);
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    blocTest<DebtsBloc, ReportState<Debts>>(
      'Debts loading to $mode',
      build: () {
        final repo = MockDebtsRepository();
        when(repo.load).thenAnswer(
          (_) async => mode == 'failure'
              ? const Failed(AppFailure(FailureKind.offline))
              : Success(
                  Snapshot(
                    DebtsModel.parse(debtsJson()),
                    'saved-stamp',
                    offline: mode == 'offline',
                  ),
                ),
        );
        return DebtsBloc(LoadDebts(repo));
      },
      act: (bloc) => bloc.add(const RefreshReport()),
      expect: () => [
        isA<ReportLoading<Debts>>(),
        switch (mode) {
          'loaded' => isA<ReportLoaded<Debts>>(),
          'offline' => isA<ReportOffline<Debts>>(),
          _ => isA<ReportFailure<Debts>>(),
        },
      ],
    );
  }
}
