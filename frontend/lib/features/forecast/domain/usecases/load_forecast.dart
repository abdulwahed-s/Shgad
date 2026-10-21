import '../../../../core/domain/snapshot.dart';
import '../../../../core/usecase/load_report.dart';
import '../../../../core/utils/result.dart';
import '../entities/forecast.dart';
import '../repositories/forecast_repository.dart';

class LoadForecast extends LoadReport<ForecastBundle> {
  LoadForecast(this.repository);
  final ForecastRepository repository;
  @override
  Future<Result<Snapshot<ForecastBundle>>> call() => repository.load();
}
