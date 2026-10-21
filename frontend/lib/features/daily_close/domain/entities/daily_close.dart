import '../../../../core/domain/amount.dart';

class CloseHistory {
  const CloseHistory(
    this.id,
    this.resolution,
    this.sourceId,
    this.voidReason,
    this.note,
  );
  final String id, resolution;
  final String? sourceId, voidReason, note;
}

class DailyClose {
  const DailyClose(
    this.date,
    this.count,
    this.previous,
    this.expected,
    this.difference,
    this.remaining,
    this.rows,
    this.history,
  );
  final String date;
  final Amount count, previous, expected, difference, remaining;
  final List<String> rows;
  final List<CloseHistory> history;
}

class ResolutionDraft {
  const ResolutionDraft(
    this.id,
    this.date,
    this.choice,
    this.amount,
    this.note,
  );
  final String id, date, choice;
  final int? amount;
  final String? note;
}

class ResolutionSaved {
  const ResolutionSaved(this.close, this.sourceId);
  final DailyClose close;
  final String? sourceId;
}
