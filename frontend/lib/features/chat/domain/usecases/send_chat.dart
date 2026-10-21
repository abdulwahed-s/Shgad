import '../../../../core/utils/result.dart';
import '../entities/chat_reply.dart';
import '../repositories/chat_repository.dart';

class SendChat {
  SendChat(this.repository);
  final ChatRepository repository;
  Future<Result<ChatReply>> call(String message, String conversationId) =>
      repository.send(message, conversationId);
}
