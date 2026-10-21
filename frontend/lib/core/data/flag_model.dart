import '../domain/review_flag.dart';
import 'amount_model.dart';

ReviewFlag parseFlag(dynamic j) => ReviewFlag(
  j['flag_id'] as String,
  j['type'] as String,
  j['reason_key'] as String,
  parseAmount(j['amount']),
  List<String>.from(j['source_ids'] as List),
  j['confidence_basis'] as String,
  j['next_step_key'] as String,
);
