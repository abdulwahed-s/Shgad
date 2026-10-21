import 'package:flutter_bloc/flutter_bloc.dart';
import '../domain/snapshot.dart';
import '../error/app_failure.dart';
import '../usecase/load_report.dart';
import '../utils/result.dart';

sealed class ReportState<T> {
  const ReportState();
}

final class ReportInitial<T> extends ReportState<T> {
  const ReportInitial();
}

final class ReportLoading<T> extends ReportState<T> {
  const ReportLoading(this.previous);
  final Snapshot<T>? previous;
}

final class ReportLoaded<T> extends ReportState<T> {
  const ReportLoaded(this.snapshot);
  final Snapshot<T> snapshot;
}

final class ReportOffline<T> extends ReportState<T> {
  const ReportOffline(this.snapshot);
  final Snapshot<T> snapshot;
}

final class ReportFailure<T> extends ReportState<T> {
  const ReportFailure(this.failure);
  final AppFailure failure;
}

class RefreshReport {
  const RefreshReport();
}

class ReportBloc<T> extends Bloc<RefreshReport, ReportState<T>> {
  ReportBloc(this.load) : super(ReportInitial<T>()) {
    on<RefreshReport>((event, emit) async {
      final previous = switch (state) {
        ReportLoaded<T>(:final snapshot) ||
        ReportOffline<T>(:final snapshot) => snapshot,
        _ => null,
      };
      emit(ReportLoading(previous));
      switch (await load()) {
        case Success<Snapshot<T>>(:final value):
          emit(value.offline ? ReportOffline(value) : ReportLoaded(value));
        case Failed<Snapshot<T>>(:final failure):
          emit(ReportFailure(failure));
      }
    });
  }
  final LoadReport<T> load;
}
