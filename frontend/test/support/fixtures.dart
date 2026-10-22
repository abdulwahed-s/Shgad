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
Map<String, dynamic> ledgerJson({
  String id = 'CNT-090',
  bool voided = false,
  String? correction,
}) => {
  'source_id': id,
  'occurred_at': '2026-09-28T21:00:00+03:00',
  'business_date': '2026-09-28',
  'type': 'CASH_SALE',
  'amount_iqd': 12000,
  'counterparty': null,
  'obligation_id': null,
  'category_id': null,
  'quantity': null,
  'status': voided ? 'voided' : 'valid',
  'import_batch_id': 'BATCH-TEST',
  'source': 'manual_entry',
  'description': 'Plain synthetic note <script>never executed</script>',
  'void': voided
      ? {
          'void_id': 'VOID-1',
          'reason': 'mistyped',
          'voided_at': '2026-10-20T10:00:00+03:00',
        }
      : null,
  'correction_of_source_id': correction,
  'raw_row': {'synthetic': true},
  'flags': <Object>[],
};
Map<String, dynamic> sourcesJson() => {
  'items': [
    {
      'kind': 'transaction',
      'source_id': 'CNT-090',
      'transaction': ledgerJson(voided: true),
      'category': null,
      'opening_balance': null,
    },
    {
      'kind': 'category',
      'source_id': 'CAT-01',
      'transaction': null,
      'category': {
        'category_id': 'CAT-01',
        'name': 'سلعة تجريبية',
        'buy_price_iqd': 1000,
        'sell_price_iqd': 5000,
      },
      'opening_balance': null,
    },
  ],
};
Map<String, dynamic> weeklyJson() => {
  'range': {'start': '2026-09-26', 'end': '2026-09-28', 'partial': true},
  'cash_sales': amount(120000, 'recorded_cash_sales'),
  'unexplained_cash_difference': amount(
    25000,
    'unexplained_cash_difference',
    kind: 'flagged',
  ),
  'credit_sales': amount(70000, 'credit_sales'),
  'collections': amount(30000, 'collections'),
  'supplier_payments': amount(10000, 'supplier_payments'),
  'operating_expenses': amount(20000, 'operating_expenses'),
  'owner_drawings': amount(10000, 'owner_drawings'),
  'capital_injections': amount(25000, 'capital_injections'),
  'outstanding_receivables': amount(150000, 'receivables'),
  'overdue_receivables': amount(30000, 'overdue_receivables'),
  'debt_aging_top': [
    {
      'counterparty_id': 'CUST-01',
      'display_name': 'أبو حيدر صاحب المحل القريب من السوق القديم',
      'outstanding': amount(150000, 'outstanding'),
      'days_overdue': 40,
    },
  ],
  'gross_margin': {
    'shown': true,
    'margin': amount(90000, 'estimated_gross_margin', kind: 'calculated'),
    'coverage_pct': 92,
    'note_key': 'margin_excludes_unrecorded_costs',
    'unexplained_difference_excluded': true,
  },
  'flags_count': 0,
  'flags': <Object>[],
  'suggestion_key': 'review_debts',
};
Map<String, dynamic> forecastJson() {
  Map<String, dynamic> scenario(int closing) => {
    'days': [
      for (var i = 0; i < 30; i++)
        {
          'date': DateTime(
            2026,
            9,
            29,
          ).add(Duration(days: i)).toIso8601String().split('T').first,
          'opening_iqd': 420000,
          'cash_sales_iqd': 12000,
          'unlinked_cash_iqd': -500,
          'collections_iqd': 0,
          'supplier_payments_iqd': 0,
          'expenses_iqd': 1000,
          'owner_drawings_iqd': 500,
          'closing_iqd': closing,
        },
    ],
    'lowest': {'date': '2026-10-01', 'closing_iqd': closing},
    'first_shortfall_date': '2026-10-01',
    'top_inflows': [
      {
        'label_key': 'cash_sales_projected',
        'amount': amount(12000, 'cash_sales_projected', kind: 'expected'),
      },
    ],
    'top_outflows': [
      {
        'label_key': 'unlinked_cash_projected',
        'amount': amount(-500, 'unlinked_cash_projected', kind: 'expected'),
      },
    ],
  };
  return {
    'as_of': '2026-09-28',
    'horizon_days': 30,
    'scenarios': {
      'base': scenario(-80000),
      'conservative': scenario(-120000),
      'stress': scenario(-230000),
    },
    'overdue_excluded': <Object>[],
    'assumption_keys': [
      'collections_expected_not_guaranteed',
      'sales_from_weekday_averages',
      'unlinked_cash_projected_from_counts',
    ],
  };
}

Map<String, dynamic> csvPreviewJson() => {
  'mapping_id': 'map-test',
  'columns': [
    {'source_header': 'Ref', 'target_field': 'source_id'},
    {'source_header': 'At', 'target_field': 'occurred_at'},
    {'source_header': 'Kind', 'target_field': 'type'},
    {'source_header': 'IQD', 'target_field': 'amount_iqd'},
  ],
  'unmapped_required': <String>[],
  'preview_rows': [
    {
      'row': 1,
      'parsed': {
        'source_id': 'CSV-1',
        'business_date': '2026-09-28',
        'type': 'CASH_SALE',
        'amount_iqd': 12000,
      },
      'errors': <Object>[],
    },
  ],
  'can_confirm': true,
};
Map<String, dynamic> csvReceiptJson() => {
  'batch_id': 'BATCH-IMPORT',
  'accepted': 1,
  'flagged_for_review': 0,
  'rejected': 0,
  'exact_duplicates': 0,
  'errors': <Object>[],
};
Map<String, dynamic> flagsJson() => {
  'items': [
    {
      'flag_id': 'FLAG-TEST',
      'type': 'suspected_duplicate',
      'reason_key': 'suspected_duplicate',
      'amount': amount(12000, 'reconciliation_amount', kind: 'flagged'),
      'source_ids': ['CNT-090'],
      'confidence_basis': 'same_amount_party_day',
      'next_step_key': 'review',
    },
  ],
};
