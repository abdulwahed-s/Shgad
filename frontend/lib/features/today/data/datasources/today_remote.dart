import '../../../../core/network/api_client.dart';

class TodayRemote {
  TodayRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load() =>
      api.get('/api/obligations/upcoming', {'days': 7});
}
