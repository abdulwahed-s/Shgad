import '../../../../core/domain/snapshot.dart';
import '../../../../core/usecase/load_report.dart';
import '../../../../core/utils/result.dart';
import '../entities/today.dart';
import '../repositories/today_repository.dart';

class LoadToday extends LoadReport<Today> {
  LoadToday(this.repository);
  final TodayRepository repository;
  @override
  Future<Result<Snapshot<Today>>> call() => repository.load();
}
