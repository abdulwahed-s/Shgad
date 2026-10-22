import '../../../../core/data/amount_model.dart';
import 'dart:convert';
import 'dart:typed_data';
import '../../../../core/domain/amount.dart';
import '../../domain/entities/csv_import.dart';

class CsvModel {
  /// Header syntax only; all row validation/calculation stays in Python.
  static List<String> headers(Uint8List bytes) {
    if (bytes.length > 5 * 1024 * 1024) throw const FormatException('CSV size');
    final text = utf8.decode(bytes);
    final result = <String>[];
    var field = StringBuffer();
    var quoted = false, closed = false;
    for (var i = 0; i < text.length; i++) {
      final c = text[i];
      if (quoted) {
        if (c == '"') {
          if (i + 1 < text.length && text[i + 1] == '"') {
            field.write('"');
            i++;
          } else {
            quoted = false;
            closed = true;
          }
        } else {
          field.write(c);
        }
        continue;
      }
      if (c == '"') {
        if (field.isNotEmpty || closed) {
          throw const FormatException('CSV quote');
        }
        quoted = true;
        continue;
      }
      if (c == ',' || c == '\n' || c == '\r') {
        result.add(field.toString());
        field = StringBuffer();
        closed = false;
        if (c != ',') break;
      } else {
        if (closed) throw const FormatException('CSV quote');
        field.write(c);
      }
      if (i == text.length - 1) result.add(field.toString());
    }
    if (quoted ||
        result.isEmpty ||
        result.length > 200 ||
        result.any((h) => h.isEmpty) ||
        result.toSet().length != result.length) {
      throw const FormatException('CSV header');
    }
    return result;
  }

  static CsvIssue issue(dynamic j) =>
      CsvIssue(j['row'] as int, j['code'] as String);
  static CsvPreview preview(Map<String, dynamic> j) => CsvPreview(
    j['mapping_id'] as String,
    (j['columns'] as List)
        .map(
          (c) => CsvColumn(
            c['source_header'] as String,
            c['target_field'] as String?,
          ),
        )
        .toList(),
    List<String>.from(j['unmapped_required'] as List),
    (j['preview_rows'] as List).map((r) {
      final p = r['parsed'];
      final value = readIqd(p?['amount_iqd']);
      return CsvPreviewRow(
        r['row'] as int,
        p?['source_id'] as String?,
        p?['business_date'] as String?,
        p?['type'] as String?,
        value == null
            ? null
            : Amount(
                value: value,
                kind: 'entered',
                label: 'preview',
                sources: const [],
                formula: '',
              ),
        (r['errors'] as List).map(issue).toList(),
      );
    }).toList(),
    j['can_confirm'] as bool,
  );
  static CsvReceipt receipt(Map<String, dynamic> j) => CsvReceipt(
    j['batch_id'] as String,
    j['accepted'] as int,
    j['flagged_for_review'] as int,
    j['rejected'] as int,
    j['exact_duplicates'] as int,
    (j['errors'] as List).map(issue).toList(),
  );
}
