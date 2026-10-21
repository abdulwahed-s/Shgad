import '../../../../core/data/amount_model.dart';
import '../../../../core/data/flag_model.dart';
import '../../domain/entities/weekly_summary.dart';

class WeeklySummaryModel {
  static WeeklySummary parse(Map<String, dynamic> j) => WeeklySummary(
    start: j['range']['start'] as String,
    end: j['range']['end'] as String,
    partial: j['range']['partial'] as bool,
    lines: [
      for (final key in [
        'cash_sales',
        'unexplained_cash_difference',
        'credit_sales',
        'collections',
        'supplier_payments',
        'operating_expenses',
        'owner_drawings',
        'capital_injections',
        'outstanding_receivables',
        'overdue_receivables',
      ])
        parseAmount(j[key]),
    ],
    margin: parseAmount(j['gross_margin']['margin']),
    marginShown: j['gross_margin']['shown'] as bool,
    coverage: j['gross_margin']['coverage_pct'] as int?,
    aging: (j['debt_aging_top'] as List)
        .map(
          (p) => AgedDebt(
            p['counterparty_id'] as String,
            p['display_name'] as String,
            parseAmount(p['outstanding']),
            p['days_overdue'] as int?,
          ),
        )
        .toList(),
    flags: (j['flags'] as List).map(parseFlag).toList(),
    suggestion: j['suggestion_key'] as String,
  );
}
