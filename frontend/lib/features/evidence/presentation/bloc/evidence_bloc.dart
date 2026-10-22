import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/domain/evidence_request.dart';
import '../../../../core/domain/new_client_id.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../../quick_entry/domain/entities/entry.dart';
import '../../../quick_entry/domain/usecases/entry_usecases.dart';
import '../../domain/entities/source_record.dart';
import '../../domain/usecases/evidence_usecases.dart';

class EvidenceView {
  const EvidenceView({
    this.request = const EvidenceRequest([], ''),
    this.records = const [],
    this.details = const {},
    this.online = true,
    this.voidSource,
    this.reason = '',
    this.voidRequestId = '',
    this.voided,
  });
  final EvidenceRequest request;
  final List<SourceRecord> records;
  final Map<String, LedgerRow> details;
  final bool online;
  final String? voidSource;
  final String reason, voidRequestId;
  final VoidedEntry? voided;
  EvidenceView copy({
    EvidenceRequest? request,
    List<SourceRecord>? records,
    Map<String, LedgerRow>? details,
    bool? online,
    String? voidSource,
    String? reason,
    String? voidRequestId,
    VoidedEntry? voided,
    bool clearVoid = false,
  }) => EvidenceView(
    request: request ?? this.request,
    records: records ?? this.records,
    details: details ?? this.details,
    online: online ?? this.online,
    voidSource: clearVoid ? null : voidSource ?? this.voidSource,
    reason: reason ?? this.reason,
    voidRequestId: voidRequestId ?? this.voidRequestId,
    voided: voided ?? this.voided,
  );
}

sealed class EvidenceState {
  const EvidenceState(this.view);
  final EvidenceView view;
}

final class EvidenceInitial extends EvidenceState {
  const EvidenceInitial(super.view);
}

final class EvidenceLoading extends EvidenceState {
  const EvidenceLoading(super.view);
}

final class EvidenceLoaded extends EvidenceState {
  const EvidenceLoaded(super.view);
}

final class EvidenceOffline extends EvidenceState {
  const EvidenceOffline(super.view);
}

final class EvidenceFailure extends EvidenceState {
  const EvidenceFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class EvidenceEvent {
  const EvidenceEvent();
}

class OpenEvidence extends EvidenceEvent {
  const OpenEvidence(this.request);
  final EvidenceRequest request;
}

class OpenSourceDetail extends EvidenceEvent {
  const OpenSourceDetail(this.id);
  final String id;
}

class BeginSourceVoid extends EvidenceEvent {
  const BeginSourceVoid(this.id);
  final String id;
}

class ChangeSourceReason extends EvidenceEvent {
  const ChangeSourceReason(this.reason);
  final String reason;
}

class ConfirmSourceVoid extends EvidenceEvent {
  const ConfirmSourceVoid();
}

class EvidenceConnection extends EvidenceEvent {
  const EvidenceConnection(this.online);
  final bool online;
}

class RecheckEvidence extends EvidenceEvent {
  const RecheckEvidence();
}

class EvidenceBloc extends Bloc<EvidenceEvent, EvidenceState> {
  EvidenceBloc(
    this.load,
    this.detail,
    this.undo,
    this.watch,
    this.check,
    this.ids,
  ) : super(EvidenceInitial(EvidenceView(online: watch.online))) {
    subscription = watch().listen((online) => add(EvidenceConnection(online)));
    on<EvidenceConnection>((event, emit) => _connect(emit, event.online));
    on<RecheckEvidence>((event, emit) async {
      _connect(emit, await check());
      if (state.view.online) add(OpenEvidence(state.view.request));
    });
    on<OpenEvidence>((event, emit) async {
      final view = state.view.copy(request: event.request);
      emit(EvidenceLoading(view));
      switch (await load(event.request.sources)) {
        case Success<List<SourceRecord>>(:final value):
          _show(emit, view.copy(records: value));
        case Failed<List<SourceRecord>>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<OpenSourceDetail>((event, emit) async {
      final view = state.view;
      emit(EvidenceLoading(view));
      switch (await detail(event.id)) {
        case Success<LedgerRow>(:final value):
          _show(emit, view.copy(details: {...view.details, value.id: value}));
        case Failed<LedgerRow>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<BeginSourceVoid>(
      (event, emit) => _show(
        emit,
        state.view.copy(voidSource: event.id, voidRequestId: ids(), reason: ''),
      ),
    );
    on<ChangeSourceReason>(
      (event, emit) => _show(
        emit,
        state.view.copy(reason: event.reason, voidRequestId: ids()),
      ),
    );
    on<ConfirmSourceVoid>((event, emit) async {
      final view = state.view;
      if (!view.online || view.voidSource == null || state is EvidenceLoading) {
        return;
      }
      if (view.reason.trim().isEmpty) {
        emit(EvidenceFailure(view, const AppFailure(FailureKind.validation)));
        return;
      }
      emit(EvidenceLoading(view));
      switch (await undo(
        view.voidSource!,
        view.voidRequestId,
        view.reason.trim(),
      )) {
        case Success<VoidedEntry>(:final value):
          switch (await load(view.request.sources)) {
            case Success<List<SourceRecord>>(value: final records):
              _show(
                emit,
                view.copy(
                  records: records,
                  details: {},
                  voided: value,
                  clearVoid: true,
                ),
              );
            case Failed<List<SourceRecord>>(:final failure):
              _failure(
                emit,
                view.copy(voided: value, clearVoid: true),
                failure,
              );
          }
        case Failed<VoidedEntry>(:final failure):
          _failure(emit, view, failure);
      }
    });
  }
  final LoadEvidence load;
  final LoadSourceDetail detail;
  final UndoEntry undo;
  final WatchConnectivity watch;
  final CheckConnectivity check;
  final NewClientId ids;
  late final StreamSubscription<bool> subscription;
  void _connect(Emitter<EvidenceState> emit, bool online) {
    final view = state.view.copy(online: online);
    emit(
      state is EvidenceLoading
          ? EvidenceLoading(view)
          : online
          ? EvidenceLoaded(view)
          : EvidenceOffline(view),
    );
  }

  void _show(Emitter<EvidenceState> emit, EvidenceView view) {
    final current = view.copy(online: watch.online);
    emit(current.online ? EvidenceLoaded(current) : EvidenceOffline(current));
  }

  void _failure(
    Emitter<EvidenceState> emit,
    EvidenceView view,
    AppFailure failure,
  ) => emit(
    failure.kind == FailureKind.offline
        ? EvidenceOffline(view.copy(online: false))
        : EvidenceFailure(view, failure),
  );
  Map<String, String> correctionFields(LedgerRow row) => {
    'type': row.type,
    'business_date': row.date,
    'amount_iqd': row.amount.value.toString(),
    'correction_of_source_id': row.id,
    if (row.partyId != null) 'counterparty_id': row.partyId!,
    if (row.obligationId != null &&
        ['CREDIT_COLLECTION', 'SUPPLIER_PAYMENT'].contains(row.type))
      'obligation_id': row.obligationId!,
  };
  @override
  Future<void> close() async {
    await subscription.cancel();
    return super.close();
  }
}
