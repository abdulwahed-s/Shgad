import '../../../../core/error/app_failure.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/chat_reply.dart';
import '../../domain/repositories/chat_repository.dart';
import '../datasources/chat_remote.dart';
import '../models/chat_model.dart';

class ChatRepositoryImpl implements ChatRepository {
  ChatRepositoryImpl(this.remote);
  final ChatRemote remote;
  @override
  Future<Result<ChatReply>> send(String message, String conversationId) async {
    try {
      return Success(
        ChatModel.parse(await remote.send(message, conversationId)),
      );
    } on ApiException catch (e) {
      return Failed(e.failure);
    } catch (_) {
      return const Failed(AppFailure(FailureKind.internal));
    }
  }
}
