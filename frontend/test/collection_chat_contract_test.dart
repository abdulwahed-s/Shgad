import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/features/chat/data/models/chat_model.dart';
import 'support/fixtures.dart';

void main() {
  test(
    'new chat action carries exact identity and tone into the shared sheet route',
    () {
      final j = chatJson()
        ..['collection_action'] = {
          'kind': 'draft',
          'counterparty_id': 'CUST-01',
          'tone': 'firm',
        };
      final result = ChatModel.parse(j);
      expect(Uri.parse(result.collectionAction!.location).queryParameters, {
        'customer': 'CUST-01',
        'tone': 'firm',
      });
    },
  );
  test('count zero proof is retained in chat evidence', () {
    final j = chatJson()
      ..['metrics'] = [
        {
          'key': 'open_flags_count',
          'value': 0,
          'unit': 'count',
          'kind': 'calculated',
          'label_key': 'brief_flags_count',
          'source_ids': <String>[],
          'formula': 'count verified flags',
          'query_evidence': {
            'tool': 'reconcile',
            'period': {'start': '2026-09-26', 'end': '2026-09-28'},
            'known_at': '2026-11-04T10:00:00Z',
            'matching_flags': 0,
          },
        },
      ];
    final result = ChatModel.parse(j);
    expect(
      result.metrics.single.queryEvidence!.originalQuery,
      contains('matching_flags'),
    );
  });
}
