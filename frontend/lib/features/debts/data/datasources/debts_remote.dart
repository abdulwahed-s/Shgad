import '../../../../core/network/api_client.dart';

class DebtsRemote {
  DebtsRemote(this.api);
  final ApiClient api;
  Future<Map<String, dynamic>> load() async {
    final receivables = await api.get('/api/debts', {
      'direction': 'receivable',
    });
    final payables = await api.get('/api/debts', {'direction': 'payable'});
    return {'receivables': receivables, 'payables': payables};
  }
}
