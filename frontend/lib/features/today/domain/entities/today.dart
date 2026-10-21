import '../../../../core/domain/amount.dart';

class ObligationItem {
  const ObligationItem(
    this.id,
    this.partyId,
    this.name,
    this.dueDate,
    this.amount,
    this.dueNow,
  );
  final String id, partyId, name, dueDate;
  final Amount amount;
  final bool dueNow;
}

class Today {
  const Today({
    required this.asOf,
    required this.start,
    required this.end,
    required this.cash,
    required this.countedAt,
    required this.dues,
    required this.expected,
    required this.confirmed,
    required this.withExpected,
    required this.dueItems,
    required this.expectedItems,
    required this.overdue,
    required this.firstConfirmed,
    required this.firstExpected,
  });
  final String asOf, start, end;
  final String? countedAt, firstConfirmed, firstExpected;
  final Amount cash, dues, expected, confirmed, withExpected;
  final List<ObligationItem> dueItems, expectedItems, overdue;
}
