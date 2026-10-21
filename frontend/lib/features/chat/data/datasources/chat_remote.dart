import '../../../../core/network/api_client.dart';

class ChatRemote {
  ChatRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> send(String message, String conversationId) =>
      api.post('/api/chat', {
        'message': message,
        'conversation_id': conversationId,
      });
}
