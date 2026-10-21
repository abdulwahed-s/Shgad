import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../entities/forecast.dart';

abstract interface class ForecastRepository {
  Future<Result<Snapshot<ForecastBundle>>> load();
}
