import '../../../../core/domain/amount.dart';
import '../../../../core/domain/known_zero_query.dart';

class ReminderAction {
  const ReminderAction(this.customerId, this.tone, this.channel, this.edited);
  final String customerId, tone, channel;
  final bool edited;
}

class CollectionCustomer {
  const CollectionCustomer({
    required this.id,
    required this.name,
    required this.overdue,
    required this.oldestDue,
    required this.daysOverdue,
    required this.reminderCount,
    required this.lastReminderDate,
    required this.daysSinceReminder,
  });
  final String id, name, oldestDue;
  final Amount overdue;
  final int daysOverdue, reminderCount;
  final String? lastReminderDate;
  final int? daysSinceReminder;
}

class CountEvidence {
  const CountEvidence(this.value, this.sources, this.formula, this.proof);
  final int value;
  final List<String> sources;
  final String formula;
  final KnownZeroQuery? proof;
}

class Collections {
  const Collections(this.asOf, this.total, this.count, this.items);
  final String asOf;
  final Amount total;
  final CountEvidence count;
  final List<CollectionCustomer> items;
}

class CollectionDraft {
  const CollectionDraft({
    required this.id,
    required this.name,
    required this.tone,
    required this.status,
    required this.text,
    required this.template,
    required this.reviewStatus,
    required this.figures,
    required this.dates,
  });
  final String id, name, tone, status, text, reviewStatus;
  final bool template;
  final List<Amount> figures;
  final Map<String, String> dates;
  bool get canShare => status == 'drafted' && reviewStatus == 'APPROVED';
}

class ReminderReceipt {
  const ReminderReceipt(
    this.id,
    this.customerId,
    this.businessDate,
    this.recordedAt,
    this.amount,
    this.channel,
  );
  final int id;
  final String customerId, businessDate, recordedAt, channel;
  final Amount amount;
}

class MorningBriefData {
  const MorningBriefData({
    required this.asOf,
    required this.weekStart,
    required this.weekEnd,
    required this.cash,
    required this.duesToday,
    required this.duesWeek,
    required this.overdue,
    required this.customerCount,
    required this.flagsCount,
    required this.topCustomers,
  });
  final String asOf, weekStart, weekEnd;
  final Amount cash, duesToday, duesWeek, overdue;
  final CountEvidence customerCount, flagsCount;
  final List<CollectionCustomer> topCustomers;
}
