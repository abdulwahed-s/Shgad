import 'dart:convert';
import '../../../../core/data/amount_model.dart';
import '../../../../core/domain/known_zero_query.dart';
import '../../domain/entities/collections.dart';

class CollectionsModel {
  static CollectionCustomer customer(dynamic j) => CollectionCustomer(
    id: j['counterparty_id'] as String,
    name: j['display_name'] as String,
    overdue: parseAmount(j['overdue_amount']),
    oldestDue: j['oldest_due_date'] as String,
    daysOverdue: j['days_overdue'] as int,
    reminderCount: j['reminder_count'] as int,
    lastReminderDate: j['last_reminder_business_date'] as String?,
    daysSinceReminder: j['days_since_last_reminder'] as int?,
  );

  static Collections collections(Map<String, dynamic> j) => Collections(
    j['as_of'] as String,
    parseAmount(j['total_overdue']),
    count(j['customer_count']),
    (j['items'] as List).map(customer).toList(),
  );

  static CountEvidence count(dynamic j) {
    final value = j['value'];
    if (value is! int || value < 0)
      throw const FormatException('Invalid sourced count');
    final sources = List<String>.from(j['source_ids'] as List);
    final rawProof = j['query_evidence'];
    KnownZeroQuery? proof;
    if (rawProof != null) {
      final q = Map<String, dynamic>.from(rawProof as Map);
      if (value != 0 ||
          sources.isNotEmpty ||
          DateTime.tryParse(q['known_at'] as String) == null)
        throw const FormatException('Invalid count proof');
      final String start, end;
      if (q['tool'] == 'get_debts' &&
          q['matching_obligations'] == 0 &&
          q['filters'] is Map) {
        start = end = q['as_of'] as String;
      } else if (q['tool'] == 'reconcile' &&
          q['matching_flags'] == 0 &&
          q['period'] is Map) {
        start = q['period']['start'] as String;
        end = q['period']['end'] as String;
      } else {
        throw const FormatException('Unknown count proof');
      }
      if (DateTime.tryParse(start) == null || DateTime.tryParse(end) == null)
        throw const FormatException('Invalid proof period');
      proof = KnownZeroQuery(
        tool: q['tool'] as String,
        start: start,
        end: end,
        matchingRows: 0,
        originalQuery: jsonEncode(q),
      );
    }
    if (sources.isEmpty && proof == null)
      throw const FormatException('Count evidence missing');
    return CountEvidence(value, sources, j['formula'] as String, proof);
  }

  static CollectionDraft draft(Map<String, dynamic> j) => CollectionDraft(
    id: j['counterparty']['id'] as String,
    name: j['counterparty']['display_name'] as String,
    tone: j['tone'] as String,
    status: j['status'] as String,
    text: j['text'] as String,
    template: j['draft_kind'] == 'template',
    reviewStatus: j['review_status'] as String,
    figures: (j['figures'] as List).map(parseAmount).toList(),
    dates: Map<String, String>.from(j['dates'] as Map),
  );

  static ReminderReceipt receipt(Map<String, dynamic> j) => ReminderReceipt(
    j['reminder_id'] as int,
    j['counterparty_id'] as String,
    j['business_date'] as String,
    j['recorded_at'] as String,
    parseAmount(j['overdue_amount']),
  );

  static MorningBriefData brief(Map<String, dynamic> j) => MorningBriefData(
    asOf: j['as_of'] as String,
    weekStart: j['week']['start'] as String,
    weekEnd: j['week']['end'] as String,
    cash: parseAmount(j['cash_on_hand']),
    duesToday: parseAmount(j['dues_today']),
    duesWeek: parseAmount(j['dues_week']),
    overdue: parseAmount(j['overdue_total']),
    customerCount: count(j['overdue_customer_count']),
    flagsCount: count(j['open_flags_count']),
    topCustomers: (j['top_customers'] as List).map(customer).toList(),
  );
}
