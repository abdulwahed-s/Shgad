import '../../../../core/utils/digit_normalizer.dart';
import '../../domain/entities/entry.dart';

abstract final class EntryModel {
  static Map<String, dynamic> payload(EntryDraft draft) {
    final party = [
      'CREDIT_SALE',
      'CREDIT_COLLECTION',
      'SUPPLIER_INVOICE',
      'SUPPLIER_PAYMENT',
    ].contains(draft.type);
    final payment = [
      'CREDIT_COLLECTION',
      'SUPPLIER_PAYMENT',
    ].contains(draft.type);
    final origin = ['CREDIT_SALE', 'SUPPLIER_INVOICE'].contains(draft.type);
    String? text(String key) {
      final value = draft.fields[key]?.trim();
      return value == null || value.isEmpty ? null : value;
    }

    return {
      'client_entry_id': draft.clientId,
      'type': draft.type,
      'business_date': DigitNormalizer.normalize(draft.date),
      'amount_iqd': DigitNormalizer.amount(draft.amountText),
      'counterparty_id': party ? text('counterparty_id') : null,
      'obligation_id': payment ? text('obligation_id') : null,
      'due_date': origin && text('due_date') != null
          ? DigitNormalizer.normalize(text('due_date')!)
          : null,
      'note': text('note'),
      'correction_of_source_id': text('correction_of_source_id'),
    };
  }

  static SavedEntry receipt(Map<String, dynamic> j) => SavedEntry(
    j['source_id'] as String,
    j['transaction_id'] as String,
    j['duplicate'] as bool,
  );
  static EntrySetup setup(Map<String, dynamic> j) =>
      EntrySetup(j['date'] as String, {
        for (final p in j['parties'] as List)
          p['counterparty_id'] as String: p['display_name'] as String,
      });
  static VoidedEntry voided(Map<String, dynamic> j) => VoidedEntry(
    j['source_id'] as String,
    j['void_id'] as String,
    j['reason'] as String,
  );
}
