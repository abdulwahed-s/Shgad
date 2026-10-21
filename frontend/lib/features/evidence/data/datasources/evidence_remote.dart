import '../../../../core/network/api_client.dart';

class EvidenceRemote {
  EvidenceRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load(List<String> ids) =>
      api.get('/api/evidence/sources', {'ids': ids.join(',')});
  Future<Map<String, dynamic>> detail(String id) =>
      api.get('/api/ledger/transactions/${Uri.encodeComponent(id)}');
}
