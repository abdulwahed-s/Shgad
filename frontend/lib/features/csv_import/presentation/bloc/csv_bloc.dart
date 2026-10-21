import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/csv_import.dart';
import '../../domain/usecases/csv_usecases.dart';

const csvTargets = [
  'source_id',
  'occurred_at',
  'type',
  'amount_iqd',
  'counterparty_id',
  'obligation_id',
  'due_date',
  'category_id',
  'quantity',
  'description',
  'currency',
  'recorded_at',
  'business_date',
];

class CsvView {
  const CsvView({
    this.selection,
    this.columns = const [],
    this.preview,
    this.receipt,
    this.dirty = true,
    this.synthetic = false,
    this.online = true,
    this.confirming = false,
  });
  final CsvSelection? selection;
  final List<CsvColumn> columns;
  final CsvPreview? preview;
  final CsvReceipt? receipt;
  final bool dirty, synthetic, online, confirming;
  bool get canConfirm =>
      preview != null && preview!.canConfirm && !dirty && synthetic;
  CsvView copy({
    CsvSelection? selection,
    List<CsvColumn>? columns,
    CsvPreview? preview,
    CsvReceipt? receipt,
    bool? dirty,
    bool? synthetic,
    bool? online,
    bool? confirming,
  }) => CsvView(
    selection: selection ?? this.selection,
    columns: columns ?? this.columns,
    preview: preview ?? this.preview,
    receipt: receipt ?? this.receipt,
    dirty: dirty ?? this.dirty,
    synthetic: synthetic ?? this.synthetic,
    online: online ?? this.online,
    confirming: confirming ?? this.confirming,
  );
}

sealed class CsvState {
  const CsvState(this.view);
  final CsvView view;
}

final class CsvInitial extends CsvState {
  const CsvInitial(super.view);
}

final class CsvLoading extends CsvState {
  const CsvLoading(super.view);
}

final class CsvLoaded extends CsvState {
  const CsvLoaded(super.view);
}

final class CsvOffline extends CsvState {
  const CsvOffline(super.view);
}

final class CsvFailure extends CsvState {
  const CsvFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class CsvEvent {
  const CsvEvent();
}

class ChooseCsv extends CsvEvent {
  const ChooseCsv();
}

class AcknowledgeSynthetic extends CsvEvent {
  const AcknowledgeSynthetic(this.value);
  final bool value;
}

class ChangeCsvColumn extends CsvEvent {
  const ChangeCsvColumn(this.header, this.target);
  final String header;
  final String? target;
}

class PreviewCsvFile extends CsvEvent {
  const PreviewCsvFile({this.suggest = false});
  final bool suggest;
}

class PrepareCsvImport extends CsvEvent {
  const PrepareCsvImport();
}

class ConfirmCsvImport extends CsvEvent {
  const ConfirmCsvImport();
}

class EditCsvMapping extends CsvEvent {
  const EditCsvMapping();
}

class NewCsvImport extends CsvEvent {
  const NewCsvImport();
}

class CsvConnection extends CsvEvent {
  const CsvConnection(this.online);
  final bool online;
}

class RecheckCsv extends CsvEvent {
  const RecheckCsv();
}

class CsvBloc extends Bloc<CsvEvent, CsvState> {
  CsvBloc(this.pick, this.preview, this.confirm, this.watch, this.check)
    : super(CsvInitial(CsvView(online: watch.online))) {
    subscription = watch().listen((online) => add(CsvConnection(online)));
    on<CsvConnection>(
      (event, emit) => _show(emit, state.view.copy(online: event.online)),
    );
    on<RecheckCsv>(
      (event, emit) async =>
          _show(emit, state.view.copy(online: await check())),
    );
    on<ChooseCsv>((event, emit) async {
      final view = state.view;
      if (!view.online || state is CsvLoading) return;
      emit(CsvLoading(view));
      switch (await pick()) {
        case Success<CsvSelection?>(:final value):
          _show(
            emit,
            value == null
                ? view
                : CsvView(
                    selection: value,
                    columns: [
                      for (final h in value.headers)
                        CsvColumn(h, csvTargets.contains(h) ? h : null),
                    ],
                    online: view.online,
                  ),
          );
        case Failed<CsvSelection?>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<AcknowledgeSynthetic>(
      (event, emit) => _show(
        emit,
        state.view.copy(synthetic: event.value, confirming: false),
      ),
    );
    on<ChangeCsvColumn>((event, emit) {
      if (state is CsvLoading ||
          !state.view.columns.any((c) => c.header == event.header) ||
          (event.target != null && !csvTargets.contains(event.target))) {
        return;
      }
      _show(
        emit,
        state.view.copy(
          columns: [
            for (final c in state.view.columns)
              c.header == event.header ? CsvColumn(c.header, event.target) : c,
          ],
          dirty: true,
          confirming: false,
        ),
      );
    });
    on<PreviewCsvFile>((event, emit) async {
      final view = state.view;
      if (!view.online ||
          view.selection == null ||
          !view.synthetic ||
          state is CsvLoading) {
        return;
      }
      emit(CsvLoading(view));
      switch (await preview(
        view.selection!,
        event.suggest ? null : view.columns,
      )) {
        case Success<CsvPreview>(:final value):
          _show(
            emit,
            view.copy(
              preview: value,
              columns: value.columns,
              dirty: false,
              confirming: false,
            ),
          );
        case Failed<CsvPreview>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<PrepareCsvImport>((event, emit) {
      if (state.view.canConfirm && state.view.online && state is! CsvLoading) {
        _show(emit, state.view.copy(confirming: true));
      }
    });
    on<EditCsvMapping>(
      (event, emit) => _show(emit, state.view.copy(confirming: false)),
    );
    on<ConfirmCsvImport>((event, emit) async {
      final view = state.view;
      if (!view.online ||
          !view.canConfirm ||
          !view.confirming ||
          state is CsvLoading) {
        return;
      }
      emit(CsvLoading(view));
      switch (await confirm(view.preview!.id)) {
        case Success<CsvReceipt>(:final value):
          _show(emit, view.copy(receipt: value, confirming: false));
        case Failed<CsvReceipt>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<NewCsvImport>(
      (event, emit) => _show(emit, CsvView(online: state.view.online)),
    );
  }
  final PickCsv pick;
  final PreviewCsv preview;
  final ConfirmCsv confirm;
  final WatchConnectivity watch;
  final CheckConnectivity check;
  late final StreamSubscription<bool> subscription;
  void _show(Emitter<CsvState> emit, CsvView view) =>
      emit(view.online ? CsvLoaded(view) : CsvOffline(view));
  void _failure(Emitter<CsvState> emit, CsvView view, AppFailure failure) =>
      emit(
        failure.kind == FailureKind.offline
            ? CsvOffline(view.copy(online: false))
            : CsvFailure(view, failure),
      );
  @override
  Future<void> close() async {
    await subscription.cancel();
    return super.close();
  }
}
