import '../../../../core/network/api_client.dart';

class SampleRemote {
  SampleRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load() => api.get('/api/meta');
  Future<Map<String, dynamic>> reset() => api.post('/api/demo/reset');
}
