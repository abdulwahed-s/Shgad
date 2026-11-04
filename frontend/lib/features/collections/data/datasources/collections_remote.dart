import '../../../../core/network/api_client.dart';

class CollectionsRemote {
  CollectionsRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load() => api.get('/api/collections');
  Future<Map<String, dynamic>> brief() => api.get('/api/brief');
  Future<Map<String, dynamic>> draft(String id, String tone) =>
      api.post('/api/collections/draft', {'counterparty_id': id, 'tone': tone});
  Future<Map<String, dynamic>> log(Map<String, dynamic> payload) =>
      api.post('/api/reminders', payload);
}
