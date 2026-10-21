import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/presentation/report_bloc.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/today/data/datasources/today_remote.dart';
import 'package:shgad/features/today/data/models/today_model.dart';
import 'package:shgad/features/today/data/repositories/today_repository_impl.dart';
import 'package:shgad/features/today/domain/entities/today.dart';
import 'package:shgad/features/today/domain/repositories/today_repository.dart';
import 'package:shgad/features/today/domain/usecases/load_today.dart';
import 'package:shgad/features/today/presentation/bloc/today_bloc.dart';
import 'core_test.dart' show MemoryCache;
import 'support/fixtures.dart';

class MockTodayRemote extends Mock implements TodayRemote {}

class MockTodayRepository extends Mock implements TodayRepository {}

void main() {
  test(
    'Today repository caches parsed response and retains count/update offline',
    () async {
      final remote = MockTodayRemote();
      final repo = TodayRepositoryImpl(remote, CachedReader(MemoryCache()));
      when(remote.load).thenAnswer((_) async => todayJson());
      final online = (await repo.load() as Success<Snapshot<Today>>).value;
      expect(online.data.cash.value, 420000);
      expect(online.data.confirmed.value, -230000);
      when(
        remote.load,
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      final offline = (await repo.load() as Success<Snapshot<Today>>).value;
      expect(offline.offline, isTrue);
      expect(offline.updatedAt, online.updatedAt);
      expect(offline.data.countedAt, online.data.countedAt);
      verify(remote.load).called(2);
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    blocTest<TodayBloc, ReportState<Today>>(
      'Today BLoC loading to $mode',
      build: () {
        final repo = MockTodayRepository();
        when(repo.load).thenAnswer(
          (_) async => mode == 'failure'
              ? const Failed(AppFailure(FailureKind.offline))
              : Success(
                  Snapshot(
                    TodayModel.parse(todayJson()),
                    'saved-stamp',
                    offline: mode == 'offline',
                  ),
                ),
        );
        return TodayBloc(LoadToday(repo));
      },
      act: (bloc) => bloc.add(const RefreshReport()),
      expect: () => [
        isA<ReportLoading<Today>>(),
        switch (mode) {
          'loaded' => isA<ReportLoaded<Today>>(),
          'offline' => isA<ReportOffline<Today>>(),
          _ => isA<ReportFailure<Today>>(),
        },
      ],
    );
  }
}
