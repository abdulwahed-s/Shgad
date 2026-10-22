import '../../../../core/network/api_client.dart';

class FlagsRemote {
  FlagsRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load() async {
    return api.get('/api/flags');
  }
}
