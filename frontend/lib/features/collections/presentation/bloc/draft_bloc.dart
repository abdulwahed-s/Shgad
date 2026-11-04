import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/domain/session_events.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/collections.dart';
import '../../domain/usecases/collections_usecases.dart';

class DraftView {
  const DraftView({
    this.customerId = '',
    this.tone = 'gentle',
    this.text = '',
    this.draft,
    this.online = true,
    this.pending,
    this.receipt,
  });
  final String customerId, tone, text;
  final CollectionDraft? draft;
  final bool online;
  final ReminderAction? pending;
  final ReminderReceipt? receipt;
  DraftView copy({
    String? customerId,
    String? tone,
    String? text,
    CollectionDraft? draft,
    bool? online,
    ReminderAction? pending,
    ReminderReceipt? receipt,
    bool clearPending = false,
    bool clearReceipt = false,
  }) => DraftView(
    customerId: customerId ?? this.customerId,
    tone: tone ?? this.tone,
    text: text ?? this.text,
    draft: draft ?? this.draft,
    online: online ?? this.online,
    pending: clearPending ? null : pending ?? this.pending,
    receipt: clearReceipt ? null : receipt ?? this.receipt,
  );
}

sealed class DraftState {
  const DraftState(this.view);
  final DraftView view;
}

final class DraftInitial extends DraftState {
  const DraftInitial(super.view);
}

final class DraftLoading extends DraftState {
  const DraftLoading(super.view);
}

final class DraftLoaded extends DraftState {
  const DraftLoaded(super.view);
}

final class DraftOffline extends DraftState {
  const DraftOffline(super.view);
}

final class DraftFailure extends DraftState {
  const DraftFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class DraftEvent {
  const DraftEvent();
}

class OpenReminder extends DraftEvent {
  const OpenReminder(this.customerId, this.tone);
  final String customerId, tone;
}

class EditReminder extends DraftEvent {
  const EditReminder(this.text);
  final String text;
}

class ShareReminder extends DraftEvent {
  const ShareReminder(this.channel);
  final String channel;
}

class RetryReminderLog extends DraftEvent {
  const RetryReminderLog();
}

class DraftConnection extends DraftEvent {
  const DraftConnection(this.online);
  final bool online;
}

class ClearReminder extends DraftEvent {
  const ClearReminder();
}

class DraftBloc extends Bloc<DraftEvent, DraftState> {
  DraftBloc(
    this.makeDraft,
    this.share,
    this.log,
    this.watch, [
    WatchSessionReset? resets,
  ]) : super(DraftInitial(DraftView(online: watch.online))) {
    _connection = watch().listen((online) => add(DraftConnection(online)));
    _resets = resets?.call().listen((_) => add(const ClearReminder()));
    on<ClearReminder>((event, emit) {
      _generation++;
      emit(DraftInitial(DraftView(online: watch.online)));
    });
    on<DraftConnection>((event, emit) {
      final view = state.view.copy(online: event.online);
      emit(
        state is DraftLoading
            ? DraftLoading(view)
            : event.online
            ? DraftLoaded(view)
            : DraftOffline(view),
      );
    });
    on<EditReminder>((event, emit) {
      if (state is DraftLoading) return;
      final view = state.view.copy(text: event.text, clearReceipt: true);
      emit(view.online ? DraftLoaded(view) : DraftOffline(view));
    });
    on<OpenReminder>((event, emit) async {
      if (state.view.pending != null) return;
      final generation = ++_generation;
      final tone = const {'gentle', 'normal', 'firm'}.contains(event.tone)
          ? event.tone
          : 'gentle';
      var view = DraftView(
        customerId: event.customerId,
        tone: tone,
        online: watch.online,
      );
      if (!view.online) {
        emit(DraftOffline(view));
        return;
      }
      emit(DraftLoading(view));
      final result = await makeDraft(event.customerId, tone);
      if (generation != _generation || emit.isDone) return;
      switch (result) {
        case Success<CollectionDraft>(:final value):
          view = view.copy(
            draft: value,
            text: value.text,
            online: watch.online,
          );
          emit(view.online ? DraftLoaded(view) : DraftOffline(view));
        case Failed<CollectionDraft>(:final failure):
          emit(DraftFailure(view.copy(online: watch.online), failure));
      }
    });
    on<ShareReminder>((event, emit) async {
      final view = state.view;
      if (state is DraftLoading ||
          view.pending != null ||
          !view.online ||
          !watch.online ||
          view.draft?.canShare != true ||
          view.text.trim().isEmpty) {
        return;
      }
      final generation = _generation;
      emit(DraftLoading(view.copy(clearReceipt: true)));
      final result = await share(view.text, event.channel);
      if (generation != _generation || emit.isDone) return;
      if (result case Failed<bool>(:final failure)) {
        emit(DraftFailure(view.copy(online: watch.online), failure));
        return;
      }
      if (result case Success<bool>(value: false)) {
        emit(
          DraftFailure(
            view,
            const AppFailure(
              FailureKind.unavailable,
              messageKey: 'collection_share_failed',
            ),
          ),
        );
        return;
      }
      final pending = ReminderAction(
        view.customerId,
        view.tone,
        event.channel,
        view.text != view.draft!.text,
      );
      await _log(
        view.copy(pending: pending, clearReceipt: true),
        emit,
        generation,
      );
    });
    on<RetryReminderLog>((event, emit) async {
      if (state is DraftLoading ||
          state.view.pending == null ||
          !watch.online) {
        return;
      }
      await _log(state.view.copy(online: true), emit, _generation);
    });
  }
  final MakeReminderDraft makeDraft;
  final ShareReminderText share;
  final LogReminder log;
  final WatchConnectivity watch;
  StreamSubscription<bool>? _connection;
  StreamSubscription<void>? _resets;
  int _generation = 0;
  Future<void> _log(
    DraftView view,
    Emitter<DraftState> emit,
    int generation,
  ) async {
    emit(DraftLoading(view));
    final result = await log(view.pending!);
    if (generation != _generation || emit.isDone) return;
    switch (result) {
      case Success<ReminderReceipt>(:final value):
        emit(
          DraftLoaded(
            view.copy(receipt: value, clearPending: true, online: watch.online),
          ),
        );
      case Failed<ReminderReceipt>(:final failure):
        emit(DraftFailure(view.copy(online: watch.online), failure));
    }
  }

  @override
  Future<void> close() async {
    await _connection?.cancel();
    await _resets?.cancel();
    return super.close();
  }
}
