import '../../../../core/utils/result.dart';
import '../entities/source_record.dart';

abstract interface class EvidenceRepository {
  Future<Result<List<SourceRecord>>> load(List<String> sources);
  Future<Result<LedgerRow>> detail(String sourceId);
}
