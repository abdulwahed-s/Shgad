import 'known_zero_query.dart';

/// A server-calculated IQD value. Null means missing; no derived money in Dart.
class Amount {
  const Amount({
    required this.value,
    required this.kind,
    required this.label,
    required this.sources,
    required this.formula,
    this.queryEvidence,
  });
  final int? value;
  final String kind;
  final String label;
  final List<String> sources;
  final String formula;
  final KnownZeroQuery? queryEvidence;
}
