import '../../l10n/generated/app_localizations.dart';

String entryTypeText(AppLocalizations l, String type) => switch (type) {
  'CASH_SALE' => l.cashSale,
  'CREDIT_SALE' => l.creditSale,
  'CREDIT_COLLECTION' => l.collection,
  'SUPPLIER_INVOICE' => l.supplierInvoice,
  'SUPPLIER_PAYMENT' => l.supplierPayment,
  'OPERATING_EXPENSE' => l.operatingExpense,
  'OWNER_DRAWING' => l.ownerDrawing,
  'CAPITAL_INJECTION' => l.capitalInjection,
  'DAILY_CASH_COUNT' => l.cashCount,
  _ => l.entryTitle,
};
