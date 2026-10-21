import '../../../../core/data/amount_model.dart';
import '../../domain/entities/debts.dart';

class DebtsModel {
  static Debts parse(Map<String, dynamic> j) =>
      Debts(_section(j['receivables']), _section(j['payables']));
  static DebtSection _section(dynamic j) => DebtSection(
    j['as_of'] as String,
    parseAmount(j['total_outstanding']),
    (j['customers'] as List)
        .map(
          (p) => DebtParty(
            p['counterparty_id'] as String,
            p['display_name'] as String,
            parseAmount(p['outstanding']),
            p['oldest_due_date'] as String?,
            (p['obligations'] as List)
                .map(
                  (o) => DebtObligation(
                    o['obligation_id'] as String,
                    parseAmount(o['original']),
                    parseAmount(o['outstanding']),
                    o['due_date'] as String?,
                    List<String>.from(o['collections'] as List),
                  ),
                )
                .toList(),
          ),
        )
        .toList(),
  );
}
