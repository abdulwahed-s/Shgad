import 'dart:convert';
import '../domain/known_zero_query.dart';

KnownZeroQuery? parseMetricProof(Map<String, dynamic> metric) {
  if (metric['query_evidence'] == null) return null;
  final q = Map<String, dynamic>.from(metric['query_evidence'] as Map);
  if (metric['value'] != 0 ||
      (metric['source_ids'] as List).isNotEmpty ||
      DateTime.tryParse(q['known_at'] as String) == null) {
    throw const FormatException('Invalid metric proof');
  }
  final String start, end;
  if (q['tool'] == 'get_debts' &&
      q['matching_obligations'] == 0 &&
      q['filters'] is Map) {
    start = end = q['as_of'] as String;
  } else if (q['tool'] == 'reconcile' &&
      q['matching_flags'] == 0 &&
      q['period'] is Map) {
    start = q['period']['start'] as String;
    end = q['period']['end'] as String;
  } else {
    throw const FormatException('Unknown metric proof');
  }
  if (DateTime.tryParse(start) == null || DateTime.tryParse(end) == null) {
    throw const FormatException('Invalid metric proof period');
  }
  return KnownZeroQuery(
    tool: q['tool'] as String,
    start: start,
    end: end,
    matchingRows: 0,
    originalQuery: jsonEncode(q),
  );
}
