import '../domain/amount.dart';

Amount parseAmount(dynamic json) {
  final map = Map<String, dynamic>.from(json as Map);
  final value = map['amount_iqd'];
  if (value != null && value is! int) {
    throw const FormatException('Non-integer IQD');
  }
  if ((map['kind'] == 'missing') != (value == null)) {
    throw const FormatException('Missing amount');
  }
  return Amount(
    value: value as int?,
    kind: map['kind'] as String,
    label: map['label_key'] as String,
    sources: List<String>.from(map['source_ids'] as List),
    formula: map['formula'] as String,
  );
}
