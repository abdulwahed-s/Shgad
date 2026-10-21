import '../../../../core/data/amount_model.dart';
import '../../domain/entities/daily_close.dart';

class CloseModel {
  static DailyClose parse(Map<String, dynamic> j) => DailyClose(
    j['date'] as String,
    parseAmount(j['count']),
    parseAmount(j['previous_count']),
    parseAmount(j['expected_close']),
    parseAmount(j['unexplained_difference']),
    parseAmount(j['remaining_difference']),
    List<String>.from(j['rows'] as List),
    (j['resolved'] as List)
        .map(
          (r) => CloseHistory(
            r['review_id'] as String,
            r['resolution'] as String,
            r['entry']?['source_id'] as String?,
            r['entry']?['void']?['reason'] as String?,
            r['note'] as String?,
          ),
        )
        .toList(),
  );
  static Map<String, dynamic> payload(ResolutionDraft draft) => {
    'client_entry_id': draft.id,
    'resolution': draft.choice,
    'amount_iqd': draft.amount,
    'note': draft.note,
  };
  static ResolutionSaved saved(Map<String, dynamic> j) => ResolutionSaved(
    parse(Map<String, dynamic>.from(j['daily_close'] as Map)),
    j['entry']?['source_id'] as String?,
  );
}
