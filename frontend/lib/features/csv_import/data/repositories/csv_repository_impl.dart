import '../../../../core/error/app_failure.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/csv_import.dart';
import '../../domain/repositories/csv_repository.dart';
import '../datasources/csv_picker.dart';
import '../datasources/csv_remote.dart';
import '../models/csv_model.dart';

class CsvRepositoryImpl implements CsvRepository {
  CsvRepositoryImpl(this.remote, this.picker);
  final CsvRemote remote;
  final CsvPicker picker;
  Future<Result<T>> _result<T>(Future<T> Function() action) async {
    try {
      return Success(await action());
    } on ApiException catch (e) {
      return Failed(e.failure);
    } on FormatException {
      return const Failed(
        AppFailure(FailureKind.validation, messageKey: 'error_import_rejected'),
      );
    } catch (_) {
      return const Failed(AppFailure(FailureKind.unavailable));
    }
  }

  @override
  Future<Result<CsvSelection?>> pick() => _result(() async {
    final file = await picker.pick();
    if (file == null) return null;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      throw const FormatException('CSV required');
    }
    return CsvSelection(file, CsvModel.headers(file.bytes));
  });
  @override
  Future<Result<CsvPreview>> preview(
    CsvSelection file,
    List<CsvColumn>? columns,
  ) => _result(
    () async => CsvModel.preview(
      await remote.preview(
        file.file,
        columns
            ?.map((c) => {'source_header': c.header, 'target_field': c.target})
            .toList(),
      ),
    ),
  );
  @override
  Future<Result<CsvReceipt>> confirm(String mappingId) =>
      _result(() async => CsvModel.receipt(await remote.confirm(mappingId)));
}
