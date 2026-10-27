import 'dart:convert';
import '../domain/amount.dart';
import '../domain/known_zero_query.dart';
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
    queryEvidence: _parseQuery(map, value),
  );
}

KnownZeroQuery? _parseQuery(Map<String, dynamic> amount, int? value) {
  if (amount['query_evidence'] == null) return null;
  final query = Map<String, dynamic>.from(amount['query_evidence'] as Map);
  if (query['tool'] == 'get_debts' && query.containsKey('schedule')) {
    return _parseScheduleQuery(amount, value, query);
  }
  if (query['tool'] == 'get_debts') {
    return _parseDebtQuery(amount, value, query);
  }
  final period = Map<String, dynamic>.from(query['period'] as Map);
  final filters = Map<String, dynamic>.from(query['filters'] as Map);
  if (value != 0 ||
      (amount['source_ids'] as List).isNotEmpty ||
      !const {'get_sales', 'reconcile'}.contains(query['tool']) ||
      query['matching_rows'] != 0 ||
      filters['active_only'] != true ||
      filters['event_types'] is! List ||
      (filters['event_types'] as List).isEmpty ||
      DateTime.tryParse(filters['known_at'] as String) == null ||
      DateTime.tryParse(period['start'] as String) == null ||
      DateTime.tryParse(period['end'] as String) == null) {
    throw const FormatException('Invalid known-zero proof');
  }
  return KnownZeroQuery(
    tool: query['tool'] as String,
    start: period['start'] as String,
    end: period['end'] as String,
    matchingRows: query['matching_rows'] as int,
    originalQuery: jsonEncode(query),
  );
}

/// D58: a zero debt total whose exact filters select no balance at `as_of`.
KnownZeroQuery _parseDebtQuery(
  Map<String, dynamic> amount,
  int? value,
  Map<String, dynamic> query,
) {
  final asOf = query['as_of'];
  if (value != 0 ||
      (amount['source_ids'] as List).isNotEmpty ||
      query['matching_obligations'] != 0 ||
      query['filters'] is! Map ||
      asOf is! String ||
      DateTime.tryParse(asOf) == null ||
      DateTime.tryParse(query['known_at'] as String) == null) {
    throw const FormatException('Invalid known-zero proof');
  }
  return KnownZeroQuery(
    tool: 'get_debts',
    start: asOf,
    end: asOf,
    matchingRows: 0,
    originalQuery: jsonEncode(query),
  );
}

/// D58: no obligation is scheduled in this upcoming window or day.
KnownZeroQuery _parseScheduleQuery(
  Map<String, dynamic> amount,
  int? value,
  Map<String, dynamic> query,
) {
  final start = query['start'];
  final end = query['end'];
  if (value != 0 ||
      (amount['source_ids'] as List).isNotEmpty ||
      query['matching_obligations'] != 0 ||
      !const {'dues', 'expected'}.contains(query['schedule']) ||
      start is! String ||
      end is! String ||
      DateTime.tryParse(start) == null ||
      DateTime.tryParse(end) == null ||
      DateTime.tryParse(query['known_at'] as String) == null) {
    throw const FormatException('Invalid known-zero proof');
  }
  return KnownZeroQuery(
    tool: 'get_debts',
    start: start,
    end: end,
    matchingRows: 0,
    originalQuery: jsonEncode(query),
  );
}
