import '../../../../core/utils/result.dart';
import '../entities/source_record.dart';
import '../repositories/evidence_repository.dart';

class LoadEvidence {
  LoadEvidence(this.repository);
  final EvidenceRepository repository;
  Future<Result<List<SourceRecord>>> call(List<String> ids) =>
      repository.load(ids);
}

class LoadSourceDetail {
  LoadSourceDetail(this.repository);
  final EvidenceRepository repository;
  Future<Result<LedgerRow>> call(String id) => repository.detail(id);
}
