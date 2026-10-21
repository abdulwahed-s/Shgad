Map<String, dynamic> amount(
  int? value,
  String label, {
  String kind = 'verified',
  List<String> ids = const ['CNT-090'],
}) => {
  'amount_iqd': value,
  'kind': value == null ? 'missing' : kind,
  'label_key': label,
  'source_ids': ids,
  'formula': 'verified source rows',
};
Map<String, dynamic> todayJson() => {
  'as_of': '2026-09-28',
  'range': {'start': '2026-09-28', 'end': '2026-10-04'},
  'cash_on_hand': amount(420000, 'cash_on_hand'),
  'counted_at': '2026-09-28T21:00:00+03:00',
  'last_synced_at': '2026-10-20T10:00:00+03:00',
  'dues_total': amount(650000, 'supplier_dues'),
  'expected_total': amount(150000, 'expected_collections', kind: 'expected'),
  'position_confirmed': amount(
    -230000,
    'position_confirmed',
    kind: 'calculated',
  ),
  'position_with_expected': amount(
    -80000,
    'position_with_expected',
    kind: 'expected',
  ),
  'dues': <Object>[],
  'expected': <Object>[],
  'overdue_receivables': <Object>[],
  'days': <Object>[],
  'first_short_date_confirmed': '2026-10-01',
  'first_short_date_with_expected': '2026-10-01',
};
Map<String, dynamic> debtsJson() {
  Map<String, dynamic> section(int total, String id) => {
    'as_of': '2026-09-28',
    'total_outstanding': amount(total, 'outstanding'),
    'aging': <String, Object>{},
    'customers': [
      {
        'counterparty_id': id,
        'display_name':
            'أبو حيدر صاحب محل المواد الغذائية والقرطاسية قرب السوق القديم',
        'outstanding': amount(total, 'outstanding'),
        'oldest_due_date': '2026-09-30',
        'days_overdue': 0,
        'bucket': 'not_due',
        'obligations': [
          {
            'obligation_id': 'OB-$id',
            'original': amount(total, 'original'),
            'outstanding': amount(total, 'outstanding'),
            'due_date': '2026-09-30',
            'collections': <String>[],
          },
        ],
      },
    ],
  };
  return {
    'receivables': section(150000, 'CUST-01'),
    'payables': section(650000, 'SUP-01'),
  };
}

Map<String, dynamic> closeJson() => {
  'date': '2026-09-28',
  'count': amount(445000, 'count'),
  'previous_count': amount(300000, 'previous_count'),
  'expected_close': amount(420000, 'expected_close', kind: 'calculated'),
  'unexplained_difference': amount(
    25000,
    'unexplained_cash_difference',
    kind: 'flagged',
  ),
  'remaining_difference': amount(
    25000,
    'unexplained_cash_difference',
    kind: 'flagged',
  ),
  'resolved': <Object>[],
  'rows': ['CNT-090'],
};
Map<String, dynamic> chatJson() => {
  'status': 'answered',
  'reply_ar':
      'عندك هسه ٤٢٠ ألف. التحصيل المتوقع ١٥٠ ألف، والنقص ٨٠ ألف إذا صار التحصيل.',
  'figures': [
    {'key': 'cash_on_hand', ...amount(420000, 'cash_on_hand')},
    {
      'key': 'expected_collection',
      ...amount(150000, 'expected_collection', kind: 'expected'),
    },
    {
      'key': 'shortfall_with_collection',
      ...amount(80000, 'shortfall_with_collection', kind: 'calculated'),
    },
  ],
  'metrics': <Object>[],
  'dates': <String, String>{},
  'contexts': [
    {
      'range': {'start': '2026-09-28', 'end': '2026-10-01'},
      'counterparty': {'id': 'CUST-01', 'display_name': 'أبو حيدر'},
    },
  ],
  'resolved_range': {'start': '2026-09-28', 'end': '2026-10-01'},
  'resolved_counterparty': {'id': 'CUST-01', 'display_name': 'أبو حيدر'},
  'clarification': null,
  'assumptions_ar': <String>[],
  'used_tools': ['forecast'],
  'renderer': {'attempts': 1, 'fell_back_to_template': false},
};
