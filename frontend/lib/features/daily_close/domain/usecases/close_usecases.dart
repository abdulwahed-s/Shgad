import '../../../../core/utils/result.dart';
import '../entities/daily_close.dart';
import '../repositories/close_repository.dart';

class LoadClose {
  LoadClose(this.repository);
  final CloseRepository repository;
  Future<Result<DailyClose>> call(String? date) => repository.load(date);
}

class ResolveClose {
  ResolveClose(this.repository);
  final CloseRepository repository;
  Future<Result<ResolutionSaved>> call(ResolutionDraft draft) =>
      repository.resolve(draft);
}
