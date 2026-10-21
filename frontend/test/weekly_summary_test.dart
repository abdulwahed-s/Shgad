import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/presentation/report_bloc.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/weekly_summary/data/datasources/weekly_summary_remote.dart';
import 'package:shgad/features/weekly_summary/data/models/weekly_summary_model.dart';
import 'package:shgad/features/weekly_summary/data/repositories/weekly_summary_repository_impl.dart';
import 'package:shgad/features/weekly_summary/domain/entities/weekly_summary.dart';
import 'package:shgad/features/weekly_summary/domain/repositories/weekly_summary_repository.dart';
import 'package:shgad/features/weekly_summary/domain/usecases/load_weekly_summary.dart';
import 'package:shgad/features/weekly_summary/presentation/bloc/weekly_summary_bloc.dart';
import 'core_test.dart' show MemoryCache;
import 'support/fixtures.dart';

class MockWeeklySummaryRemote extends Mock implements WeeklySummaryRemote {}

class MockWeeklySummaryRepository extends Mock
    implements WeeklySummaryRepository {}

void main() {
  test(
    'WeeklySummary repository maps real response, caches and retains timestamp offline',
    () async {
      final remote = MockWeeklySummaryRemote();
      final repo = WeeklySummaryRepositoryImpl(
        remote,
        CachedReader(MemoryCache()),
      );
      when(remote.load).thenAnswer((_) async => weeklyJson());
      final online =
          (await repo.load() as Success<Snapshot<WeeklySummary>>).value;
      when(
        remote.load,
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      final offline =
          (await repo.load() as Success<Snapshot<WeeklySummary>>).value;
      expect(offline.offline, isTrue);
      expect(offline.updatedAt, online.updatedAt);
      verify(remote.load).called(2);
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    blocTest<WeeklySummaryBloc, ReportState<WeeklySummary>>(
      'WeeklySummary loading to $mode',
      build: () {
        final repo = MockWeeklySummaryRepository();
        when(repo.load).thenAnswer(
          (_) async => mode == 'failure'
              ? const Failed(AppFailure(FailureKind.offline))
              : Success(
                  Snapshot(
                    WeeklySummaryModel.parse(weeklyJson()),
                    'saved-stamp',
                    offline: mode == 'offline',
                  ),
                ),
        );
        return WeeklySummaryBloc(LoadWeeklySummary(repo));
      },
      act: (bloc) => bloc.add(const RefreshReport()),
      expect: () => [
        isA<ReportLoading<WeeklySummary>>(),
        switch (mode) {
          'loaded' => isA<ReportLoaded<WeeklySummary>>(),
          'offline' => isA<ReportOffline<WeeklySummary>>(),
          _ => isA<ReportFailure<WeeklySummary>>(),
        },
      ],
    );
  }
}
