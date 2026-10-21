import '../../../../core/domain/session_events.dart';
import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/domain/connectivity.dart';
import '../../../../core/domain/new_client_id.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/chat_reply.dart';
import '../../domain/usecases/send_chat.dart';

class ChatView {
  const ChatView({
    this.draft = '',
    this.turns = const [],
    this.online = true,
    this.revision = 0,
  });
  final String draft;
  final List<ChatTurn> turns;
  final bool online;
  final int revision;
  ChatView copy({
    String? draft,
    List<ChatTurn>? turns,
    bool? online,
    int? revision,
  }) => ChatView(
    draft: draft ?? this.draft,
    turns: turns ?? this.turns,
    online: online ?? this.online,
    revision: revision ?? this.revision,
  );
}

sealed class ChatState {
  const ChatState(this.view);
  final ChatView view;
}

final class ChatInitial extends ChatState {
  const ChatInitial(super.view);
}

final class ChatLoading extends ChatState {
  const ChatLoading(super.view);
}

final class ChatLoaded extends ChatState {
  const ChatLoaded(super.view);
}

final class ChatOffline extends ChatState {
  const ChatOffline(super.view);
}

final class ChatFailure extends ChatState {
  const ChatFailure(super.view, this.failure);
  final AppFailure failure;
}

sealed class ChatEvent {
  const ChatEvent();
}

class TypeChat extends ChatEvent {
  const TypeChat(this.text);
  final String text;
}

class FillChat extends ChatEvent {
  const FillChat(this.text);
  final String text;
}

class SubmitChat extends ChatEvent {
  const SubmitChat();
}

class ChooseChatOption extends ChatEvent {
  const ChooseChatOption(this.question, this.option);
  final String question;
  final ChatOption option;
}

class ChatConnection extends ChatEvent {
  const ChatConnection(this.online);
  final bool online;
}

class RecheckChat extends ChatEvent {
  const RecheckChat();
}

class ClearChat extends ChatEvent {
  const ClearChat();
}

class ChatBloc extends Bloc<ChatEvent, ChatState> {
  ChatBloc(
    this.send,
    this.watch,
    this.check,
    NewClientId ids, [
    WatchSessionReset? resets,
  ]) : conversationId = ids(),
       super(ChatInitial(ChatView(online: watch.online))) {
    _resets = resets?.call().listen((_) => add(const ClearChat()));
    on<ClearChat>((event, emit) {
      conversationId = ids();
      _show(
        emit,
        ChatView(online: watch.online, revision: state.view.revision + 1),
      );
    });
    subscription = watch().listen((online) => add(ChatConnection(online)));
    on<ChatConnection>(
      (event, emit) => _show(emit, state.view.copy(online: event.online)),
    );
    on<RecheckChat>(
      (event, emit) async =>
          _show(emit, state.view.copy(online: await check())),
    );
    on<TypeChat>((event, emit) {
      if (state is! ChatLoading) {
        _show(emit, state.view.copy(draft: event.text));
      }
    });
    on<FillChat>((event, emit) {
      if (state is! ChatLoading) {
        _show(
          emit,
          state.view.copy(draft: event.text, revision: state.view.revision + 1),
        );
      }
    });
    on<ChooseChatOption>((event, emit) {
      if (state is! ChatLoading) {
        _show(
          emit,
          state.view.copy(
            draft:
                '${event.question}\n${event.option.label} (${event.option.value})',
            revision: state.view.revision + 1,
          ),
        );
      }
    });
    on<SubmitChat>((event, emit) async {
      final view = state.view;
      final message = view.draft.trim();
      if (!view.online || state is ChatLoading) return;
      if (message.isEmpty || message.length > 4000) {
        emit(ChatFailure(view, const AppFailure(FailureKind.validation)));
        return;
      }
      emit(ChatLoading(view));
      switch (await send(message, conversationId)) {
        case Success<ChatReply>(:final value):
          _show(
            emit,
            view.copy(
              draft: '',
              revision: view.revision + 1,
              turns: [...view.turns, ChatTurn(message, value)],
            ),
          );
        case Failed<ChatReply>(:final failure):
          emit(
            failure.kind == FailureKind.offline
                ? ChatOffline(view.copy(online: false))
                : ChatFailure(view, failure),
          );
      }
    });
  }
  final SendChat send;
  final WatchConnectivity watch;
  final CheckConnectivity check;
  String conversationId;
  StreamSubscription<void>? _resets;
  late final StreamSubscription<bool> subscription;
  void _show(Emitter<ChatState> emit, ChatView view) =>
      emit(view.online ? ChatLoaded(view) : ChatOffline(view));
  @override
  Future<void> close() async {
    await _resets?.cancel();
    await subscription.cancel();
    return super.close();
  }
}
