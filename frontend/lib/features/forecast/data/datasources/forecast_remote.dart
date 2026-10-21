import '../../../../core/network/api_client.dart';

class ForecastRemote {
  ForecastRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load() async {
    return api.get('/api/reports/forecast', {'scenario': 'all'});
  }
}
