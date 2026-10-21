import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/new_client_id.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/chat/data/datasources/chat_remote.dart';
import 'package:shgad/features/chat/data/models/chat_model.dart';
import 'package:shgad/features/chat/data/repositories/chat_repository_impl.dart';
import 'package:shgad/features/chat/domain/entities/chat_reply.dart';
import 'package:shgad/features/chat/domain/repositories/chat_repository.dart';
import 'package:shgad/features/chat/domain/usecases/send_chat.dart';
import 'package:shgad/features/chat/presentation/bloc/chat_bloc.dart';
import 'entry_test.dart' show FakeConnection;
import 'support/fixtures.dart';

class MockChatRemote extends Mock implements ChatRemote {}

class MockChatRepository extends Mock implements ChatRepository {}

void main() {
  late MockChatRepository repo;
  late FakeConnection connection;
  ChatBloc build() => ChatBloc(
    SendChat(repo),
    WatchConnectivity(connection),
    CheckConnectivity(connection),
    NewClientId(),
  );
  setUp(() {
    repo = MockChatRepository();
    connection = FakeConnection();
    when(
      () => repo.send(any(), any()),
    ).thenAnswer((_) async => Success(ChatModel.parse(chatJson())));
  });
  tearDown(() => connection.controller.close());
  test(
    'Chat repository preserves rendered text, figures and resolved context verbatim',
    () async {
      final remote = MockChatRemote();
      final repository = ChatRepositoryImpl(remote);
      when(
        () => remote.send('سؤالي', 'conversation'),
      ).thenAnswer((_) async => chatJson());
      final reply =
          (await repository.send('سؤالي', 'conversation') as Success<ChatReply>)
              .value;
      expect(reply.text, chatJson()['reply_ar']);
      expect(reply.resolved!.partyId, 'CUST-01');
      expect(reply.resolved!.end, '2026-10-01');
      expect(reply.figures.first.value, 420000);
      when(
        () => remote.send(any(), any()),
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      expect(
        await repository.send('سؤالي', 'conversation'),
        isA<Failed<ChatReply>>(),
      );
    },
  );
  blocTest<ChatBloc, ChatState>(
    'Chat draft, loading and server-rendered response',
    build: build,
    act: (bloc) async {
      bloc.add(const TypeChat('سؤالي'));
      await Future<void>.delayed(Duration.zero);
      bloc.add(const SubmitChat());
    },
    expect: () => [
      isA<ChatLoaded>(),
      isA<ChatLoading>(),
      isA<ChatLoaded>().having(
        (s) => s.view.turns.single.reply.text,
        'unchanged text',
        chatJson()['reply_ar'],
      ),
    ],
  );
  blocTest<ChatBloc, ChatState>(
    'Chat typed failure retains question',
    build: () {
      when(() => repo.send(any(), any())).thenAnswer(
        (_) async => const Failed(AppFailure(FailureKind.unavailable)),
      );
      return build();
    },
    act: (bloc) async {
      bloc.add(const TypeChat('سؤالي'));
      await Future<void>.delayed(Duration.zero);
      bloc.add(const SubmitChat());
    },
    expect: () => [
      isA<ChatLoaded>(),
      isA<ChatLoading>(),
      isA<ChatFailure>().having((s) => s.view.draft, 'question', 'سؤالي'),
    ],
  );
  blocTest<ChatBloc, ChatState>(
    'Offline chat keeps draft and never queues on reconnect',
    build: build,
    act: (bloc) async {
      bloc.add(const TypeChat('سؤالي'));
      await Future<void>.delayed(Duration.zero);
      connection.set(false);
      await bloc.stream.firstWhere((s) => s is ChatOffline);
      bloc.add(const SubmitChat());
      await Future<void>.delayed(Duration.zero);
      connection.set(true);
    },
    expect: () => [
      isA<ChatLoaded>(),
      isA<ChatOffline>(),
      isA<ChatLoaded>().having((s) => s.view.draft, 'question', 'سؤالي'),
    ],
    verify: (_) => verifyNever(() => repo.send(any(), any())),
  );
}
