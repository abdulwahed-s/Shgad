import '../../../../core/data/amount_model.dart';
import '../../domain/entities/today.dart';

class TodayModel {
  static Today parse(Map<String, dynamic> json) => Today(
    asOf: json['as_of'] as String,
    start: json['range']['start'] as String,
    end: json['range']['end'] as String,
    cash: parseAmount(json['cash_on_hand']),
    countedAt: json['counted_at'] as String?,
    dues: parseAmount(json['dues_total']),
    expected: parseAmount(json['expected_total']),
    confirmed: parseAmount(json['position_confirmed']),
    withExpected: parseAmount(json['position_with_expected']),
    dueItems: _items(json['dues']),
    expectedItems: _items(json['expected']),
    overdue: _items(json['overdue_receivables']),
    firstConfirmed: json['first_short_date_confirmed'] as String?,
    firstExpected: json['first_short_date_with_expected'] as String?,
  );
  static List<ObligationItem> _items(dynamic items) => (items as List)
      .map(
        (j) => ObligationItem(
          j['obligation_id'] as String,
          j['counterparty']['id'] as String,
          j['counterparty']['display_name'] as String,
          j['due_date'] as String,
          parseAmount(j['outstanding']),
          j['due_now'] == true,
        ),
      )
      .toList();
}
