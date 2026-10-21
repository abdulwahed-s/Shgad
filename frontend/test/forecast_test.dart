import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/forecast/data/datasources/forecast_remote.dart';
import 'package:shgad/features/forecast/data/models/forecast_model.dart';
import 'package:shgad/features/forecast/data/repositories/forecast_repository_impl.dart';
import 'package:shgad/features/forecast/domain/entities/forecast.dart';
import 'package:shgad/features/forecast/domain/repositories/forecast_repository.dart';
import 'package:shgad/features/forecast/domain/usecases/load_forecast.dart';
import 'package:shgad/features/forecast/presentation/bloc/forecast_bloc.dart';
import 'core_test.dart' show MemoryCache;
import 'support/fixtures.dart';

class MockForecastRemote extends Mock implements ForecastRemote {}

class MockForecastRepository extends Mock implements ForecastRepository {}

void main() {
  test(
    'Forecast repository preserves all three thirty-day estimates and cache time',
    () async {
      final remote = MockForecastRemote();
      final repo = ForecastRepositoryImpl(remote, CachedReader(MemoryCache()));
      when(remote.load).thenAnswer((_) async => forecastJson());
      final online =
          (await repo.load() as Success<Snapshot<ForecastBundle>>).value;
      expect(online.data.scenarios.keys, {'base', 'conservative', 'stress'});
      expect(online.data.scenarios['base']!.days.length, 30);
      expect(online.data.scenarios['stress']!.days.first.closing, -230000);
      when(
        remote.load,
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      final offline =
          (await repo.load() as Success<Snapshot<ForecastBundle>>).value;
      expect(offline.offline, isTrue);
      expect(offline.updatedAt, online.updatedAt);
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    blocTest<ForecastBloc, ForecastState>(
      'Forecast loading to $mode',
      build: () {
        final repo = MockForecastRepository();
        when(repo.load).thenAnswer(
          (_) async => mode == 'failure'
              ? const Failed(AppFailure(FailureKind.missing))
              : Success(
                  Snapshot(
                    ForecastModel.parse(forecastJson()),
                    'saved-stamp',
                    offline: mode == 'offline',
                  ),
                ),
        );
        return ForecastBloc(LoadForecast(repo));
      },
      act: (b) => b.add(const RefreshForecast()),
      expect: () => [
        isA<ForecastLoading>(),
        switch (mode) {
          'loaded' => isA<ForecastLoaded>(),
          'offline' => isA<ForecastOffline>(),
          _ => isA<ForecastFailure>(),
        },
      ],
    );
  }
  test(
    'Scenario changes select server data; display geometry never mutates financial values',
    () async {
      final repo = MockForecastRepository();
      final data = ForecastModel.parse(forecastJson());
      when(
        repo.load,
      ).thenAnswer((_) async => Success(Snapshot(data, 'saved-stamp')));
      final bloc = ForecastBloc(LoadForecast(repo));
      bloc.add(const RefreshForecast());
      await bloc.stream.firstWhere((s) => s is ForecastLoaded);
      bloc.add(const ChooseScenario('stress'));
      await bloc.stream.firstWhere((s) => s.view.scenario == 'stress');
      expect(bloc.state.view.dayAmount('closing').value, -230000);
      expect(bloc.state.view.dayAmount('difference').value, -500);
      expect(
        bloc.state.view.trace!.points.every(
          (p) => p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1,
        ),
        isTrue,
      );
      expect(data.scenarios['base']!.days.first.closing, -80000);
      await bloc.close();
    },
  );
  test('Incomplete scenario/horizon fails instead of inventing data', () {
    final json = forecastJson();
    json['scenarios']['stress']['days'] = <Object>[];
    expect(() => ForecastModel.parse(json), throwsFormatException);
  });
}
