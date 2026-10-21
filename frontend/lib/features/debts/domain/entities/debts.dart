import '../../../../core/domain/amount.dart';

class DebtObligation {
  const DebtObligation(
    this.id,
    this.original,
    this.outstanding,
    this.due,
    this.collections,
  );
  final String id;
  final Amount original, outstanding;
  final String? due;
  final List<String> collections;
}

class DebtParty {
  const DebtParty(
    this.id,
    this.name,
    this.outstanding,
    this.due,
    this.obligations,
  );
  final String id, name;
  final Amount outstanding;
  final String? due;
  final List<DebtObligation> obligations;
}

class DebtSection {
  const DebtSection(this.asOf, this.total, this.parties);
  final String asOf;
  final Amount total;
  final List<DebtParty> parties;
}

class Debts {
  const Debts(this.receivables, this.payables);
  final DebtSection receivables, payables;
}
