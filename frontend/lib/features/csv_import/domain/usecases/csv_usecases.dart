import '../../../../core/utils/result.dart';
import '../entities/csv_import.dart';
import '../repositories/csv_repository.dart';

class PickCsv {
  PickCsv(this.repository);
  final CsvRepository repository;
  Future<Result<CsvSelection?>> call() => repository.pick();
}

class PreviewCsv {
  PreviewCsv(this.repository);
  final CsvRepository repository;
  Future<Result<CsvPreview>> call(
    CsvSelection file,
    List<CsvColumn>? columns,
  ) => repository.preview(file, columns);
}

class ConfirmCsv {
  ConfirmCsv(this.repository);
  final CsvRepository repository;
  Future<Result<CsvReceipt>> call(String id) => repository.confirm(id);
}
