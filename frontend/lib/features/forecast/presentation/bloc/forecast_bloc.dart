import 'dart:async';
import '../../../../core/domain/session_events.dart';
import '../../../../core/domain/connectivity.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/amount.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/forecast.dart';
import '../../domain/usecases/load_forecast.dart';

class ChartPoint {
  const ChartPoint(this.x, this.y);
  final double x, y;
}

class ChartTrace {
  const ChartTrace(this.points, this.zeroY, this.shortfallIndex);
  final List<ChartPoint> points;
  final double zeroY;
  final int? shortfallIndex;
  static ChartTrace fromScenario(ForecastScenario scenario) {
    // Display geometry only. IQD stays integer in every entity; these ratios
    // are pixel positions, never financial figures, forecasts or totals.
    var floor = 0, ceiling = 0;
    for (final day in scenario.days) {
      if (day.closing < floor) floor = day.closing;
      if (day.closing > ceiling) ceiling = day.closing;
    }
    final span = ceiling - floor;
    final points = <ChartPoint>[];
    for (var i = 0; i < scenario.days.length; i++) {
      points.add(
        ChartPoint(
          i / (scenario.days.length - 1),
          span == 0 ? 0.5 : (ceiling - scenario.days[i].closing) / span,
        ),
      );
    }
    final short = scenario.days.indexWhere((d) => d.date == scenario.shortfall);
    return ChartTrace(
      points,
      span == 0 ? 0.5 : ceiling / span,
      short < 0 ? null : short,
    );
  }
}

class ForecastView {
  const ForecastView({
    this.snapshot,
    this.scenario = 'base',
    this.dayIndex = 0,
    this.trace,
  });
  final Snapshot<ForecastBundle>? snapshot;
  final String scenario;
  final int dayIndex;
  final ChartTrace? trace;
  ForecastScenario? get selected => snapshot?.data.scenarios[scenario];
  ForecastDay? get day => selected?.days[dayIndex];
  // These values are unchanged integers from the server's forecast day.
  Amount dayAmount(String field) => Amount(
    value: switch (field) {
      'sales' => day!.sales,
      'difference' => day!.difference,
      _ => day!.closing,
    },
    kind: 'expected',
    label: field,
    sources: const [],
    formula: '',
  );
  ForecastView choose(String name, int index) => ForecastView(
    snapshot: snapshot,
    scenario: name,
    dayIndex: index,
    trace: snapshot == null
        ? null
        : ChartTrace.fromScenario(snapshot!.data.scenarios[name]!),
  );
}

sealed class ForecastState {
  const ForecastState(this.view);
  final ForecastView view;
}

final class ForecastInitial extends ForecastState {
  const ForecastInitial(super.view);
}

final class ForecastLoading extends ForecastState {
  const ForecastLoading(super.view);
}

final class ForecastLoaded extends ForecastState {
  const ForecastLoaded(super.view);
}

final class ForecastOffline extends ForecastState {
  const ForecastOffline(super.view);
}

final class ForecastFailure extends ForecastState {
  const ForecastFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class ForecastEvent {
  const ForecastEvent();
}

class RefreshForecast extends ForecastEvent {
  const RefreshForecast({this.clear = false, this.online});
  final bool clear;
  final bool? online;
}

class ChooseScenario extends ForecastEvent {
  const ChooseScenario(this.name);
  final String name;
}

class ChooseForecastDay extends ForecastEvent {
  const ChooseForecastDay(this.date);
  final String date;
}

class ForecastBloc extends Bloc<ForecastEvent, ForecastState> {
  ForecastBloc(
    this.load, [
    WatchSessionReset? resets,
    WatchLedgerChanges? changes,
    WatchConnectivity? connectivity,
  ]) : super(const ForecastInitial(ForecastView())) {
    _resets = resets?.call().listen((_) {
      _generation++;
      add(const RefreshForecast(clear: true));
    });
    _changes = changes?.call().listen((_) {
      _generation++;
      add(const RefreshForecast());
    });
    _connection = connectivity?.call().listen(
      (online) => add(RefreshForecast(online: online)),
    );
    on<RefreshForecast>((event, emit) async {
      final request = ++_generation;
      final old = event.clear ? const ForecastView() : state.view;
      if (event.online == false && old.snapshot != null) {
        final snapshot = old.snapshot!;
        _show(
          emit,
          ForecastView(
            snapshot: Snapshot(
              snapshot.data,
              snapshot.updatedAt,
              offline: true,
            ),
            scenario: old.scenario,
            dayIndex: old.dayIndex,
            trace: old.trace,
          ),
        );
        return;
      }
      emit(ForecastLoading(old));
      final result = await load();
      if (request != _generation) return;
      switch (result) {
        case Success<Snapshot<ForecastBundle>>(:final value):
          final view = ForecastView(
            snapshot: value,
            scenario: old.scenario,
            dayIndex: old.dayIndex,
          ).choose(old.scenario, old.dayIndex);
          _show(emit, view);
        case Failed<Snapshot<ForecastBundle>>(:final failure):
          emit(ForecastFailure(old, failure));
      }
    });
    on<ChooseScenario>((event, emit) {
      if (!['base', 'conservative', 'stress'].contains(event.name) ||
          state.view.snapshot == null) {
        return;
      }
      _show(emit, state.view.choose(event.name, state.view.dayIndex));
    });
    on<ChooseForecastDay>((event, emit) {
      final view = state.view;
      final index =
          view.selected?.days.indexWhere((d) => d.date == event.date) ?? -1;
      if (index >= 0) _show(emit, view.choose(view.scenario, index));
    });
  }
  final LoadForecast load;
  int _generation = 0;
  StreamSubscription<void>? _resets;
  StreamSubscription<void>? _changes;
  StreamSubscription<bool>? _connection;
  @override
  Future<void> close() async {
    await _resets?.cancel();
    await _changes?.cancel();
    await _connection?.cancel();
    return super.close();
  }

  void _show(Emitter<ForecastState> emit, ForecastView view) => emit(
    view.snapshot!.offline ? ForecastOffline(view) : ForecastLoaded(view),
  );
}
