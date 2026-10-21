import '../../../../core/utils/result.dart';
import '../entities/daily_close.dart';

abstract interface class CloseRepository {
  Future<Result<DailyClose>> load(String? date);
  Future<Result<ResolutionSaved>> resolve(ResolutionDraft draft);
}
