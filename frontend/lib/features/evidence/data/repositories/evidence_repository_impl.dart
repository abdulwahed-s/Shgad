import '../../../../core/error/app_failure.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/source_record.dart';
import '../../domain/repositories/evidence_repository.dart';
import '../datasources/evidence_remote.dart';
import '../models/source_model.dart';

class EvidenceRepositoryImpl implements EvidenceRepository {
  EvidenceRepositoryImpl(this.remote);
  final EvidenceRemote remote;
  Future<Result<T>> _result<T>(Future<T> Function() action) async {
    try {
      return Success(await action());
    } on ApiException catch (e) {
      return Failed(e.failure);
    } catch (_) {
      return const Failed(AppFailure(FailureKind.internal));
    }
  }

  @override
  Future<Result<List<SourceRecord>>> load(List<String> sources) => _result(
    () async {
      final unique = sources.toSet().toList();
      final result = <SourceRecord>[];
      for (var start = 0; start < unique.length; start += 100) {
        final end = start + 100 > unique.length ? unique.length : start + 100;
        final json = await remote.load(unique.sublist(start, end));
        final records = (json['items'] as List).map(SourceModel.parse).toList();
        if (records.length != end - start ||
            records.map((r) => r.id).toSet().length != records.length ||
            records.any((r) => !unique.sublist(start, end).contains(r.id))) {
          throw const FormatException('Incomplete evidence');
        }
        result.addAll(records);
      }
      return result;
    },
  );
  @override
  Future<Result<LedgerRow>> detail(String sourceId) =>
      _result(() async => SourceModel.row(await remote.detail(sourceId)));
}
