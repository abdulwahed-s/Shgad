import '../../../../core/domain/session_events.dart';
import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/domain/amount.dart';
import '../../../../core/domain/new_client_id.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/digit_normalizer.dart';
import '../../../../core/utils/result.dart';
import '../../../quick_entry/domain/entities/entry.dart';
import '../../../quick_entry/domain/usecases/entry_usecases.dart';
import '../../domain/entities/daily_close.dart';
import '../../domain/usecases/close_usecases.dart';

const resolutionChoices = [
  'leave_unexplained',
  'cash_sale_unitemized',
  'capital_injection',
  'expense_unrecorded',
  'owner_drawing_unrecorded',
];

class CloseView {
  const CloseView({
    this.data,
    this.choice,
    this.amount = '',
    this.note = '',
    this.clientId = '',
    this.confirm = false,
    this.online = true,
    this.recording = false,
    this.sourceId,
    this.saved = false,
    this.undoing = false,
    this.reason = '',
    this.undoId = '',
    this.voided,
    this.entered,
  });
  final DailyClose? data;
  final String? choice, sourceId;
  final String amount, note, clientId, reason, undoId;
  final bool confirm, online, recording, saved, undoing;
  final VoidedEntry? voided;
  final Amount? entered;
  CloseView copy({
    DailyClose? data,
    String? choice,
    String? amount,
    String? note,
    String? clientId,
    bool? confirm,
    bool? online,
    bool? recording,
    String? sourceId,
    bool? saved,
    bool? undoing,
    String? reason,
    String? undoId,
    VoidedEntry? voided,
    Amount? entered,
  }) => CloseView(
    data: data ?? this.data,
    choice: choice ?? this.choice,
    amount: amount ?? this.amount,
    note: note ?? this.note,
    clientId: clientId ?? this.clientId,
    confirm: confirm ?? this.confirm,
    online: online ?? this.online,
    recording: recording ?? this.recording,
    sourceId: sourceId ?? this.sourceId,
    saved: saved ?? this.saved,
    undoing: undoing ?? this.undoing,
    reason: reason ?? this.reason,
    undoId: undoId ?? this.undoId,
    voided: voided ?? this.voided,
    entered: entered ?? this.entered,
  );
}

sealed class CloseState {
  const CloseState(this.view);
  final CloseView view;
}

final class CloseInitial extends CloseState {
  const CloseInitial(super.view);
}

final class CloseLoading extends CloseState {
  const CloseLoading(super.view);
}

final class CloseLoaded extends CloseState {
  const CloseLoaded(super.view);
}

final class CloseOffline extends CloseState {
  const CloseOffline(super.view);
}

final class CloseFailure extends CloseState {
  const CloseFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class CloseEvent {
  const CloseEvent();
}

class OpenClose extends CloseEvent {
  const OpenClose([this.date]);
  final String? date;
}

class ChangeResolution extends CloseEvent {
  const ChangeResolution(this.key, this.value);
  final String key, value;
}

class PrepareResolution extends CloseEvent {
  const PrepareResolution();
}

class ConfirmResolution extends CloseEvent {
  const ConfirmResolution();
}

class EditResolution extends CloseEvent {
  const EditResolution();
}

class ChooseClosePanel extends CloseEvent {
  const ChooseClosePanel(this.recording);
  final bool recording;
}

class CloseConnection extends CloseEvent {
  const CloseConnection(this.online);
  final bool online;
}

class RecheckClose extends CloseEvent {
  const RecheckClose();
}

class BeginReviewUndo extends CloseEvent {
  const BeginReviewUndo();
}

class ChangeReviewReason extends CloseEvent {
  const ChangeReviewReason(this.reason);
  final String reason;
}

class ConfirmReviewUndo extends CloseEvent {
  const ConfirmReviewUndo();
}

class CloseBloc extends Bloc<CloseEvent, CloseState> {
  CloseBloc(
    this.load,
    this.resolve,
    this.undo,
    this.watch,
    this.check,
    this.ids, [
    WatchSessionReset? resets,
  ]) : super(CloseInitial(CloseView(online: watch.online))) {
    _resets = resets?.call().listen((_) => add(const OpenClose()));
    subscription = watch().listen((online) => add(CloseConnection(online)));
    on<CloseConnection>(
      (event, emit) => _show(emit, state.view.copy(online: event.online)),
    );
    on<RecheckClose>(
      (event, emit) async =>
          _show(emit, state.view.copy(online: await check())),
    );
    on<OpenClose>((event, emit) async {
      final view = state.view;
      emit(CloseLoading(view));
      switch (await load(event.date)) {
        case Success<DailyClose>(:final value):
          _show(emit, view.copy(data: value, clientId: ids()));
        case Failed<DailyClose>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<ChooseClosePanel>(
      (event, emit) => _show(emit, state.view.copy(recording: event.recording)),
    );
    on<ChangeResolution>((event, emit) {
      if (state is CloseLoading) return;
      final view = switch (event.key) {
        'choice' => state.view.copy(
          choice: event.value,
          confirm: false,
          clientId: ids(),
        ),
        'amount' => state.view.copy(
          amount: event.value,
          confirm: false,
          clientId: ids(),
        ),
        _ => state.view.copy(
          note: event.value,
          confirm: false,
          clientId: ids(),
        ),
      };
      _show(emit, view);
    });
    on<EditResolution>(
      (event, emit) => _show(emit, state.view.copy(confirm: false)),
    );
    on<PrepareResolution>((event, emit) {
      final view = state.view;
      if (!view.online || state is CloseLoading) return;
      if (!resolutionChoices.contains(view.choice) ||
          (view.choice != 'leave_unexplained' &&
              DigitNormalizer.amount(view.amount) == null)) {
        emit(CloseFailure(view, const AppFailure(FailureKind.validation)));
        return;
      }
      _show(
        emit,
        view.copy(
          confirm: true,
          entered: view.choice == 'leave_unexplained'
              ? null
              : Amount(
                  value: DigitNormalizer.amount(view.amount),
                  kind: 'entered',
                  label: 'input',
                  sources: const [],
                  formula: '',
                ),
        ),
      );
    });
    on<ConfirmResolution>((event, emit) async {
      final view = state.view;
      if (!view.online ||
          !view.confirm ||
          view.data == null ||
          state is CloseLoading) {
        return;
      }
      emit(CloseLoading(view));
      final draft = ResolutionDraft(
        view.clientId,
        view.data!.date,
        view.choice!,
        view.choice == 'leave_unexplained'
            ? null
            : DigitNormalizer.amount(view.amount),
        view.note.trim().isEmpty ? null : view.note.trim(),
      );
      switch (await resolve(draft)) {
        case Success<ResolutionSaved>(:final value):
          _show(
            emit,
            CloseView(
              data: value.close,
              online: view.online,
              sourceId: value.sourceId,
              saved: true,
              clientId: ids(),
            ),
          );
        case Failed<ResolutionSaved>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<BeginReviewUndo>(
      (event, emit) =>
          _show(emit, state.view.copy(undoing: true, undoId: ids())),
    );
    on<ChangeReviewReason>(
      (event, emit) =>
          _show(emit, state.view.copy(reason: event.reason, undoId: ids())),
    );
    on<ConfirmReviewUndo>((event, emit) async {
      final view = state.view;
      if (!view.online ||
          !view.undoing ||
          view.sourceId == null ||
          state is CloseLoading) {
        return;
      }
      if (view.reason.trim().isEmpty) {
        emit(CloseFailure(view, const AppFailure(FailureKind.validation)));
        return;
      }
      emit(CloseLoading(view));
      switch (await undo(view.sourceId!, view.undoId, view.reason.trim())) {
        case Success<VoidedEntry>(:final value):
          switch (await load(view.data!.date)) {
            case Success<DailyClose>(value: final data):
              _show(emit, view.copy(data: data, voided: value, undoing: false));
            case Failed<DailyClose>(:final failure):
              _failure(emit, view.copy(voided: value, undoing: false), failure);
          }
        case Failed<VoidedEntry>(:final failure):
          _failure(emit, view, failure);
      }
    });
  }
  final LoadClose load;
  final ResolveClose resolve;
  final UndoEntry undo;
  final WatchConnectivity watch;
  final CheckConnectivity check;
  final NewClientId ids;
  StreamSubscription<void>? _resets;
  late final StreamSubscription<bool> subscription;
  void _show(Emitter<CloseState> emit, CloseView view) =>
      emit(view.online ? CloseLoaded(view) : CloseOffline(view));
  void _failure(Emitter<CloseState> emit, CloseView view, AppFailure failure) =>
      emit(
        failure.kind == FailureKind.offline
            ? CloseOffline(view.copy(online: false))
            : CloseFailure(view, failure),
      );
  @override
  Future<void> close() async {
    await _resets?.cancel();
    await subscription.cancel();
    return super.close();
  }
}
