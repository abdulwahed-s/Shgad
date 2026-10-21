import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../entities/weekly_summary.dart';

abstract interface class WeeklySummaryRepository {
  Future<Result<Snapshot<WeeklySummary>>> load();
}
