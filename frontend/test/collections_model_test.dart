import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/features/collections/data/models/collections_model.dart';

Map<String, dynamic> collectionAmount([int value = 47000]) => {
  'amount_iqd': value,
  'kind': 'calculated',
  'label_key': 'outstanding',
  'source_ids': ['LATE'],
  'formula': 'original - active collections',
};

Map<String, dynamic> collectionCustomer() => {
  'counterparty_id': 'CUST-01',
  'display_name': 'أم نور',
  'overdue_amount': collectionAmount(),
  'oldest_due_date': '2026-09-20',
  'days_overdue': 8,
  'source_ids': ['LATE'],
  'reminder_count': 2,
  'last_reminder_business_date': '2026-09-27',
  'days_since_last_reminder': 1,
};

Map<String, dynamic> sourcedCount([int value = 1]) => {
  'key': 'overdue_customer_count',
  'value': value,
  'unit': 'count',
  'kind': 'calculated',
  'label_key': 'overdue_customer_count',
  'source_ids': ['LATE'],
  'formula': 'count distinct overdue customers',
};

Map<String, dynamic> collectionsJson() => {
  'as_of': '2026-09-28',
  'total_overdue': collectionAmount(),
  'customer_count': sourcedCount(),
  'items': [collectionCustomer()],
};

Map<String, dynamic> collectionDraftJson({bool template = false}) => {
  'status': 'drafted',
  'counterparty': {'id': 'CUST-01', 'display_name': 'أم نور'},
  'tone': 'gentle',
  'text': 'هلا أم نور، المبلغ المتأخر ٤٧ ألف دينار.',
  'draft_kind': template ? 'template' : 'model',
  'figures': [collectionAmount()],
  'metrics': [],
  'dates': {'oldest_due': '2026-09-20'},
  'renderer': {'attempts': 1, 'fell_back_to_template': template},
  'review_status': 'PENDING_REVIEW',
};

void main() {
  test(
    'collection model preserves server order, amounts and reminder ages',
    () {
      final source = collectionsJson();
      (source['items'] as List).add({
        ...collectionCustomer(),
        'counterparty_id': 'CUST-02',
      });
      final result = CollectionsModel.collections(source);
      expect(result.items.map((p) => p.id), ['CUST-01', 'CUST-02']);
      expect(result.items.first.overdue.value, 47000);
      expect(result.items.first.daysSinceReminder, 1);
      expect(result.items.first.reminderCount, 2);
    },
  );

  test('draft preserves server text and pending template share gate', () {
    final model = CollectionsModel.draft(collectionDraftJson());
    final template = CollectionsModel.draft(
      collectionDraftJson(template: true),
    );
    expect(model.text, collectionDraftJson()['text']);
    expect(model.canShare, isTrue);
    expect(template.canShare, isFalse);
  });

  test('count zero retains exact empty flag proof', () {
    final proof = {
      'tool': 'reconcile',
      'period': {'start': '2026-09-26', 'end': '2026-09-28'},
      'known_at': '2026-11-04T10:00:00+00:00',
      'matching_flags': 0,
    };
    final count = CollectionsModel.count({
      ...sourcedCount(0),
      'source_ids': <String>[],
      'query_evidence': proof,
    });
    expect(count.value, 0);
    expect(count.proof!.originalQuery, contains('matching_flags'));
  });

  test('fractional money and missing counts never become zero', () {
    final source = collectionsJson();
    (source['total_overdue'] as Map)['amount_iqd'] = 4.7;
    expect(() => CollectionsModel.collections(source), throwsFormatException);
    expect(
      () => CollectionsModel.count({...sourcedCount(), 'value': null}),
      throwsFormatException,
    );
  });
}
