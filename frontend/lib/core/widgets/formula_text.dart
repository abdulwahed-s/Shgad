import '../../l10n/generated/app_localizations.dart';
import 'entry_type_text.dart';

/// Exact presentation translations only. Ambiguous and new formulas retain an
/// honest fallback; the unmodified server formula is always inspectable.
String formulaText(AppLocalizations l, String raw) {
  if (raw.isEmpty ||
      (RegExp(r'[\u0600-\u06ff]').hasMatch(raw) &&
          !RegExp('[A-Za-z]').hasMatch(raw))) {
    return raw;
  }
  final known = <String, String>{
    'FINANCIAL_RULES §2: latest count/opening + later cash flows':
        l.formulaCash,
    'cash_on_hand - supplier_dues': l.formulaConfirmed,
    'cash_on_hand + non-overdue expected collections - supplier_dues':
        l.formulaExpected,
    'count[d] - (count[d-1] + recorded inflows[d] - recorded outflows[d])':
        l.formulaDifference,
    'count[d-1] + recorded inflows[d] - recorded outflows[d]': l.formulaClose,
    'closing DAILY_CASH_COUNT[d-1]': l.previousCount,
    'closing DAILY_CASH_COUNT[d]': l.cashCount,
    'FINANCIAL_RULES §4: priced sales - sum(quantity * category buy price)':
        l.formulaMargin,
    'original amount - active verified allocations': l.formulaDebt,
    'recorded obligation amount': l.formulaOriginal,
    'sum non-overdue expected collections due on this date':
        l.formulaCollections,
    'same amount, party and day on distinct source identities': l.basisSameDay,
    'source rows': l.savedEntryFormula,
  };
  if (known.containsKey(raw)) {
    return known[raw]!;
  }
  final recorded = RegExp(
    r'^sum active recorded (CASH_SALE|CREDIT_SALE|CREDIT_COLLECTION|SUPPLIER_PAYMENT|OPERATING_EXPENSE|OWNER_DRAWING|CAPITAL_INJECTION) in resolved range$',
  ).firstMatch(raw);
  if (recorded != null) {
    return l.formulaRecorded(entryTypeText(l, recorded.group(1)!));
  }
  final projected = RegExp(
    r'^FINANCIAL_RULES §6: sum projected (cash_sales|unlinked_cash|collections|expenses|owner_drawings|supplier_payments) (inflows|outflows) over 30 days$',
  ).firstMatch(raw);
  if (projected != null) {
    final type = switch (projected.group(1)) {
      'cash_sales' => l.recordedSalesDriver,
      'unlinked_cash' => l.projectedDifference,
      'collections' => l.expectedCollections,
      'expenses' => l.operatingExpense,
      'owner_drawings' => l.ownerDrawing,
      _ => l.supplierPayment,
    };
    return l.formulaProjected(type);
  }
  return l.formulaUnavailable;
}
