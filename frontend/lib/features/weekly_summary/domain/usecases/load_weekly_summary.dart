import '../../../../core/domain/snapshot.dart';
import '../../../../core/usecase/load_report.dart';
import '../../../../core/utils/result.dart';
import '../entities/weekly_summary.dart';
import '../repositories/weekly_summary_repository.dart';

class LoadWeeklySummary extends LoadReport<WeeklySummary> {
  LoadWeeklySummary(this.repository);
  final WeeklySummaryRepository repository;
  @override
  Future<Result<Snapshot<WeeklySummary>>> call() => repository.load();
}
