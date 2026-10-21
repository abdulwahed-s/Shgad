import '../../../../core/utils/result.dart';
import '../entities/csv_import.dart';

abstract interface class CsvRepository {
  Future<Result<CsvSelection?>> pick();
  Future<Result<CsvPreview>> preview(
    CsvSelection file,
    List<CsvColumn>? columns,
  );
  Future<Result<CsvReceipt>> confirm(String mappingId);
}
