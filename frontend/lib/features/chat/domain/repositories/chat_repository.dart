import '../../../../core/utils/result.dart';
import '../entities/chat_reply.dart';

abstract interface class ChatRepository {
  Future<Result<ChatReply>> send(String message, String conversationId);
}
