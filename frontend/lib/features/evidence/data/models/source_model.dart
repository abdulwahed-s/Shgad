import 'dart:convert';
import '../../../../core/domain/amount.dart';
import '../../domain/entities/source_record.dart';

class SourceModel {
  static Amount _amount(dynamic value, String id, String kind) => Amount(
    value: value as int?,
    kind: value == null ? 'missing' : kind,
    label: 'source',
    sources: [id],
    formula: 'recorded source amount',
  );
  static LedgerRow row(Map<String, dynamic> j) => LedgerRow(
    id: j['source_id'] as String,
    date: j['business_date'] as String,
    type: j['type'] as String,
    amount: _amount(
      j['amount_iqd'],
      j['source_id'] as String,
      j['status'] == 'valid' ? 'verified' : 'flagged',
    ),
    status: j['status'] as String,
    description: j['description'] as String,
    partyId: j['counterparty']?['id'] as String?,
    partyName: j['counterparty']?['display_name'] as String?,
    obligationId: j['obligation_id'] as String?,
    voidId: j['void']?['void_id'] as String?,
    voidReason: j['void']?['reason'] as String?,
    voidedAt: j['void']?['voided_at'] as String?,
    correctionOf: j['correction_of_source_id'] as String?,
    rawText: j['raw_row'] == null
        ? ''
        : const JsonEncoder.withIndent('  ').convert(j['raw_row']),
  );
  static SourceRecord parse(dynamic j) {
    final id = j['source_id'] as String;
    final kind = j['kind'] as String;
    return SourceRecord(
      id: id,
      kind: kind,
      row: j['transaction'] == null
          ? null
          : row(Map<String, dynamic>.from(j['transaction'] as Map)),
      opening: kind == 'opening_balance'
          ? _amount(j['opening_balance']['amount_iqd'], id, 'verified')
          : null,
      buy: kind == 'category'
          ? _amount(j['category']['buy_price_iqd'], id, 'verified')
          : null,
      sell: kind == 'category'
          ? _amount(j['category']['sell_price_iqd'], id, 'verified')
          : null,
      name: j['category']?['name'] as String?,
      date: j['opening_balance']?['business_date'] as String?,
      rawText: kind == 'transaction'
          ? ''
          : const JsonEncoder.withIndent('  ').convert(j[kind]),
    );
  }
}
