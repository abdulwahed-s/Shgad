import '../../../../core/network/api_client.dart';

class EntryRemote {
  EntryRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> setup() async {
    final meta = await api.get('/api/meta');
    final receivable = await api.get('/api/debts', {'direction': 'receivable'});
    final payable = await api.get('/api/debts', {'direction': 'payable'});
    return {
      'date': meta['business_as_of'],
      'parties': [
        ...receivable['customers'] as List,
        ...payable['customers'] as List,
      ],
    };
  }

  Future<Map<String, dynamic>> save(Map<String, dynamic> body) =>
      api.post('/api/entries', body);
  Future<Map<String, dynamic>> undo(
    String sourceId,
    Map<String, dynamic> body,
  ) => api.post('/api/entries/${Uri.encodeComponent(sourceId)}/void', body);
}
