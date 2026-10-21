import '../../../../core/network/api_client.dart';

class CloseRemote {
  CloseRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load(String? date) async {
    date ??= (await api.get('/api/meta'))['business_as_of'] as String;
    return api.get('/api/daily-close/${Uri.encodeComponent(date)}');
  }

  Future<Map<String, dynamic>> resolve(
    String date,
    Map<String, dynamic> body,
  ) => api.post('/api/daily-close/${Uri.encodeComponent(date)}/resolve', body);
}
