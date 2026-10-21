import '../../../../core/domain/session_events.dart';
import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/amount.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/domain/new_client_id.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/digit_normalizer.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/entry.dart';
import '../../domain/usecases/entry_usecases.dart';

const entryTypes = [
  'CASH_SALE',
  'CREDIT_SALE',
  'CREDIT_COLLECTION',
  'SUPPLIER_INVOICE',
  'SUPPLIER_PAYMENT',
  'OPERATING_EXPENSE',
  'OWNER_DRAWING',
  'CAPITAL_INJECTION',
  'DAILY_CASH_COUNT',
];

enum EntryMode { edit, confirm, saved, undo, voided }

class EntryView {
  const EntryView(
    this.draft, {
    this.mode = EntryMode.edit,
    this.online = true,
    this.parties = const {},
    this.saved,
    this.voided,
    this.reason = '',
    this.undoId = '',
    this.amount,
  });
  final EntryDraft draft;
  final EntryMode mode;
  final bool online;
  final Map<String, String> parties;
  final SavedEntry? saved;
  final VoidedEntry? voided;
  final String reason, undoId;
  final Amount? amount;
  bool get needsParty => [
    'CREDIT_SALE',
    'CREDIT_COLLECTION',
    'SUPPLIER_INVOICE',
    'SUPPLIER_PAYMENT',
  ].contains(draft.type);
  bool get needsObligation =>
      ['CREDIT_COLLECTION', 'SUPPLIER_PAYMENT'].contains(draft.type);
  bool get needsDue => ['CREDIT_SALE', 'SUPPLIER_INVOICE'].contains(draft.type);
  String get partyName =>
      parties[draft.fields['counterparty_id']] ??
      draft.fields['counterparty_id'] ??
      '';
  EntryView copy({
    EntryDraft? draft,
    EntryMode? mode,
    bool? online,
    Map<String, String>? parties,
    SavedEntry? saved,
    VoidedEntry? voided,
    String? reason,
    String? undoId,
    Amount? amount,
  }) => EntryView(
    draft ?? this.draft,
    mode: mode ?? this.mode,
    online: online ?? this.online,
    parties: parties ?? this.parties,
    saved: saved ?? this.saved,
    voided: voided ?? this.voided,
    reason: reason ?? this.reason,
    undoId: undoId ?? this.undoId,
    amount: amount ?? this.amount,
  );
}

sealed class EntryState {
  const EntryState(this.view);
  final EntryView view;
}

final class EntryInitial extends EntryState {
  const EntryInitial(super.view);
}

final class EntryLoading extends EntryState {
  const EntryLoading(super.view);
}

final class EntryLoaded extends EntryState {
  const EntryLoaded(super.view);
}

final class EntryOffline extends EntryState {
  const EntryOffline(super.view);
}

final class EntryFailure extends EntryState {
  const EntryFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class EntryEvent {
  const EntryEvent();
}

class OpenEntry extends EntryEvent {
  const OpenEntry([this.fields = const {}]);
  final Map<String, String> fields;
}

class ChangeEntry extends EntryEvent {
  const ChangeEntry(this.key, this.value);
  final String key, value;
}

class PrepareEntry extends EntryEvent {
  const PrepareEntry();
}

class ConfirmEntry extends EntryEvent {
  const ConfirmEntry();
}

class EditEntry extends EntryEvent {
  const EditEntry();
}

class BeginUndo extends EntryEvent {
  const BeginUndo();
}

class ChangeUndoReason extends EntryEvent {
  const ChangeUndoReason(this.reason);
  final String reason;
}

class ConfirmUndo extends EntryEvent {
  const ConfirmUndo();
}

class EntryConnection extends EntryEvent {
  const EntryConnection(this.online);
  final bool online;
}

class RecheckEntry extends EntryEvent {
  const RecheckEntry();
}

class EntryBloc extends Bloc<EntryEvent, EntryState> {
  EntryBloc(
    this.load,
    this.save,
    this.undo,
    this.watch,
    this.check,
    this.ids, [
    WatchSessionReset? resets,
  ]) : super(
         EntryInitial(
           EntryView(EntryDraft(ids(), const {}), online: watch.online),
         ),
       ) {
    _resets = resets?.call().listen((_) => add(const OpenEntry()));
    _connection = watch().listen((online) => add(EntryConnection(online)));
    on<EntryConnection>(
      (event, emit) => emit(
        event.online
            ? EntryLoaded(state.view.copy(online: true))
            : EntryOffline(state.view.copy(online: false)),
      ),
    );
    on<RecheckEntry>((event, emit) async {
      final online = await check();
      emit(
        online
            ? EntryLoaded(state.view.copy(online: true))
            : EntryOffline(state.view.copy(online: false)),
      );
    });
    on<OpenEntry>((event, emit) async {
      final view = EntryView(
        EntryDraft(ids(), {'type': 'CASH_SALE', ...event.fields}),
        online: watch.online,
      );
      emit(EntryLoading(view));
      switch (await load()) {
        case Success<EntrySetup>(:final value):
          emit(
            EntryLoaded(
              view.copy(
                draft: EntryDraft(view.draft.clientId, {
                  'business_date': value.date,
                  ...view.draft.fields,
                }),
                parties: value.parties,
              ),
            ),
          );
        case Failed<EntrySetup>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<ChangeEntry>((event, emit) {
      if (state is EntryLoading) return;
      final draft = EntryDraft(ids(), {
        ...state.view.draft.fields,
        event.key: event.value,
      });
      final view = state.view.copy(draft: draft, mode: EntryMode.edit);
      emit(view.online ? EntryLoaded(view) : EntryOffline(view));
    });
    on<PrepareEntry>((event, emit) {
      final view = state.view;
      if (!view.online || state is EntryLoading) return;
      final amount = DigitNormalizer.amount(view.draft.amountText);
      final date = DigitNormalizer.normalize(view.draft.date);
      if (amount == null ||
          !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(date) ||
          !entryTypes.contains(view.draft.type) ||
          (view.needsParty &&
              (view.draft.fields['counterparty_id'] ?? '').trim().isEmpty) ||
          (view.needsObligation &&
              (view.draft.fields['obligation_id'] ?? '').trim().isEmpty) ||
          (view.needsDue &&
              (view.draft.fields['due_date'] ?? '').trim().isEmpty)) {
        emit(EntryFailure(view, const AppFailure(FailureKind.validation)));
        return;
      }
      emit(
        EntryLoaded(
          view.copy(
            mode: EntryMode.confirm,
            amount: Amount(
              value: amount,
              kind: 'entered',
              label: view.draft.type,
              sources: const [],
              formula: '',
            ),
          ),
        ),
      );
    });
    on<EditEntry>(
      (event, emit) => emit(EntryLoaded(state.view.copy(mode: EntryMode.edit))),
    );
    on<ConfirmEntry>((event, emit) async {
      final view = state.view;
      if (!view.online ||
          state is EntryLoading ||
          view.mode != EntryMode.confirm) {
        return;
      }
      emit(EntryLoading(view));
      switch (await save(view.draft)) {
        case Success<SavedEntry>(:final value):
          emit(EntryLoaded(view.copy(mode: EntryMode.saved, saved: value)));
        case Failed<SavedEntry>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<BeginUndo>((event, emit) {
      if (state.view.saved == null || !state.view.online) return;
      emit(EntryLoaded(state.view.copy(mode: EntryMode.undo, undoId: ids())));
    });
    on<ChangeUndoReason>(
      (event, emit) => emit(EntryLoaded(state.view.copy(reason: event.reason))),
    );
    on<ConfirmUndo>((event, emit) async {
      final view = state.view;
      if (!view.online ||
          state is EntryLoading ||
          view.mode != EntryMode.undo ||
          view.saved == null) {
        return;
      }
      if (view.reason.trim().isEmpty) {
        emit(EntryFailure(view, const AppFailure(FailureKind.validation)));
        return;
      }
      emit(EntryLoading(view));
      switch (await undo(
        view.saved!.sourceId,
        view.undoId,
        view.reason.trim(),
      )) {
        case Success<VoidedEntry>(:final value):
          emit(EntryLoaded(view.copy(mode: EntryMode.voided, voided: value)));
        case Failed<VoidedEntry>(:final failure):
          _failure(emit, view, failure);
      }
    });
  }
  final LoadEntrySetup load;
  final SaveEntry save;
  final UndoEntry undo;
  final WatchConnectivity watch;
  final CheckConnectivity check;
  final NewClientId ids;
  StreamSubscription<void>? _resets;
  late final StreamSubscription<bool> _connection;
  void _failure(Emitter<EntryState> emit, EntryView view, AppFailure failure) =>
      emit(
        failure.kind == FailureKind.offline
            ? EntryOffline(view.copy(online: false))
            : EntryFailure(view, failure),
      );
  @override
  Future<void> close() async {
    await _resets?.cancel();
    await _connection.cancel();
    return super.close();
  }
}
