import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/sample_shop.dart';
import '../../domain/usecases/sample_usecases.dart';

class SampleView {
  const SampleView({
    this.shop,
    this.online = true,
    this.confirm = false,
    this.saved = false,
  });
  final SampleShop? shop;
  final bool online, confirm, saved;
  SampleView copy({
    SampleShop? shop,
    bool? online,
    bool? confirm,
    bool? saved,
  }) => SampleView(
    shop: shop ?? this.shop,
    online: online ?? this.online,
    confirm: confirm ?? this.confirm,
    saved: saved ?? this.saved,
  );
}

sealed class SampleState {
  const SampleState(this.view);
  final SampleView view;
}

final class SampleInitial extends SampleState {
  const SampleInitial(super.view);
}

final class SampleLoading extends SampleState {
  const SampleLoading(super.view);
}

final class SampleLoaded extends SampleState {
  const SampleLoaded(super.view);
}

final class SampleOffline extends SampleState {
  const SampleOffline(super.view);
}

final class SampleFailure extends SampleState {
  const SampleFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class SampleEvent {
  const SampleEvent();
}

class OpenSample extends SampleEvent {
  const OpenSample();
}

class PrepareSampleReset extends SampleEvent {
  const PrepareSampleReset();
}

class ConfirmSampleReset extends SampleEvent {
  const ConfirmSampleReset();
}

class CancelSampleReset extends SampleEvent {
  const CancelSampleReset();
}

class SampleConnection extends SampleEvent {
  const SampleConnection(this.online);
  final bool online;
}

class RecheckSample extends SampleEvent {
  const RecheckSample();
}

class SampleBloc extends Bloc<SampleEvent, SampleState> {
  SampleBloc(this.load, this.reset, this.watch, this.check)
    : super(SampleInitial(SampleView(online: watch.online))) {
    subscription = watch().listen((online) => add(SampleConnection(online)));
    on<SampleConnection>((event, emit) => _connect(emit, event.online));
    on<RecheckSample>((event, emit) async {
      _connect(emit, await check());
      if (state.view.online) add(const OpenSample());
    });
    on<OpenSample>((event, emit) async {
      final view = state.view;
      emit(SampleLoading(view));
      switch (await load()) {
        case Success<SampleShop>(:final value):
          _show(emit, view.copy(shop: value));
        case Failed<SampleShop>(:final failure):
          _failure(emit, view, failure);
      }
    });
    on<PrepareSampleReset>(
      (event, emit) =>
          _show(emit, state.view.copy(confirm: true, saved: false)),
    );
    on<CancelSampleReset>(
      (event, emit) => _show(emit, state.view.copy(confirm: false)),
    );
    on<ConfirmSampleReset>((event, emit) async {
      final view = state.view;
      if (!view.online || !view.confirm || state is SampleLoading) return;
      emit(SampleLoading(view));
      switch (await reset()) {
        case Success<String>():
          _show(emit, view.copy(saved: true, confirm: false));
        case Failed<String>(:final failure):
          _failure(emit, view, failure);
      }
    });
  }
  final LoadSampleShop load;
  final ResetSampleShop reset;
  final WatchConnectivity watch;
  final CheckConnectivity check;
  late final StreamSubscription<bool> subscription;
  void _connect(Emitter<SampleState> emit, bool online) {
    final view = state.view.copy(online: online);
    emit(
      state is SampleLoading
          ? SampleLoading(view)
          : online
          ? SampleLoaded(view)
          : SampleOffline(view),
    );
  }

  void _show(Emitter<SampleState> emit, SampleView view) {
    final current = view.copy(online: watch.online);
    emit(current.online ? SampleLoaded(current) : SampleOffline(current));
  }

  void _failure(
    Emitter<SampleState> emit,
    SampleView view,
    AppFailure failure,
  ) => emit(
    failure.kind == FailureKind.offline
        ? SampleOffline(view.copy(online: false))
        : SampleFailure(view, failure),
  );
  @override
  Future<void> close() async {
    await subscription.cancel();
    return super.close();
  }
}
