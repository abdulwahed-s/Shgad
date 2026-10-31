import '../../../../core/domain/amount.dart';
import '../../../../core/domain/picked_file.dart';

class CsvSelection {
  const CsvSelection(this.file, this.headers);
  final PickedFile file;
  final List<String> headers;
}

class CsvColumn {
  const CsvColumn(this.header, this.target);
  final String header;
  final String? target;
}

class CsvIssue {
  const CsvIssue(this.row, this.code, {this.field, this.candidates = const []});
  final int row;
  final String code;
  final String? field;
  final List<CsvCandidate> candidates;
}

class CsvCandidate {
  const CsvCandidate(this.id, this.displayName);
  final String id, displayName;
}

class CsvPreviewRow {
  const CsvPreviewRow(
    this.row,
    this.sourceId,
    this.date,
    this.type,
    this.amount,
    this.issues,
  );
  final int row;
  final String? sourceId, date, type;
  final Amount? amount;
  final List<CsvIssue> issues;
}

class CsvPreview {
  const CsvPreview(
    this.id,
    this.columns,
    this.missing,
    this.rows,
    this.canConfirm,
  );
  final String id;
  final List<CsvColumn> columns;
  final List<String> missing;
  final List<CsvPreviewRow> rows;
  final bool canConfirm;
}

class CsvReceipt {
  const CsvReceipt(
    this.id,
    this.accepted,
    this.flagged,
    this.rejected,
    this.duplicates,
    this.issues,
  );
  final String id;
  final int accepted, flagged, rejected, duplicates;
  final List<CsvIssue> issues;
}
