import '../../../../core/data/amount_model.dart';
import '../../../../core/data/metric_proof_model.dart';
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
    final map = Map<String, dynamic>.from(j as Map);
    final value = map['value'];
    if (value is! int || value < 0) {
      throw const FormatException('Invalid sourced count');
    }
    final sources = List<String>.from(map['source_ids'] as List);
    final proof = parseMetricProof(map);
    if (sources.isEmpty && proof == null) {
      throw const FormatException('Count evidence missing');
    }
    return CountEvidence(value, sources, map['formula'] as String, proof);
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
    j['channel'] as String,
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
