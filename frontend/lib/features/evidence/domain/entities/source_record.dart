import '../../../../core/domain/amount.dart';

class SourceRecord {
  const SourceRecord({
    required this.id,
    required this.kind,
    this.row,
    this.opening,
    this.buy,
    this.sell,
    this.name,
    this.date,
    this.rawText = '',
  });
  final String id, kind;
  final LedgerRow? row;
  final Amount? opening, buy, sell;
  final String? name, date;
  final String rawText;
}

class LedgerRow {
  const LedgerRow({
    required this.id,
    required this.date,
    required this.type,
    required this.amount,
    required this.status,
    required this.description,
    required this.partyId,
    required this.partyName,
    required this.obligationId,
    required this.voidId,
    required this.voidReason,
    required this.voidedAt,
    required this.correctionOf,
    required this.rawText,
  });
  final String id, date, type, status, description, rawText;
  final Amount amount;
  final String? partyId,
      partyName,
      obligationId,
      voidId,
      voidReason,
      voidedAt,
      correctionOf;
}
