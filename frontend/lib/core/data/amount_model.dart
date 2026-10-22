import '../domain/amount.dart';
import '../constants/data_limits.dart';
import '../error/app_failure.dart';

int? readIqd(dynamic value) {
  if (value == null) return null;
  if (value is! int) throw const FormatException('Non-integer IQD');
  if (value > DataLimits.maxExactIqd || value < -DataLimits.maxExactIqd) {
    throw const IqdFormatException();
  }
  return value;
}

int readRequiredIqd(dynamic value) =>
    readIqd(value) ?? (throw const FormatException('Missing IQD'));

Amount parseAmount(dynamic json) {
  final map = Map<String, dynamic>.from(json as Map);
  final value = readIqd(map['amount_iqd']);
  if ((map['kind'] == 'missing') != (value == null)) {
    throw const FormatException('Missing amount');
  }
  return Amount(
    value: value,
    kind: map['kind'] as String,
    label: map['label_key'] as String,
    sources: List<String>.from(map['source_ids'] as List),
    formula: map['formula'] as String,
  );
}
