import '../../../../core/utils/digit_normalizer.dart';
import '../../domain/entities/entry.dart';

abstract final class EntryModel {
  static Map<String, dynamic> payload(EntryDraft draft) => {
    'client_entry_id': draft.clientId,
    'type': draft.type,
    'business_date': DigitNormalizer.normalize(draft.date),
    'amount_iqd': DigitNormalizer.amount(draft.amountText),
    for (final key in [
      'counterparty_id',
      'obligation_id',
      'due_date',
      'note',
      'correction_of_source_id',
    ])
      key: (draft.fields[key]?.trim().isEmpty ?? true)
          ? null
          : key == 'due_date'
          ? DigitNormalizer.normalize(draft.fields[key]!.trim())
          : draft.fields[key]!.trim(),
  };
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
