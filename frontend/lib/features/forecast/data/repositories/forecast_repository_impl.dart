import '../../../../core/data/cached_reader.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/forecast.dart';
import '../../domain/repositories/forecast_repository.dart';
import '../datasources/forecast_remote.dart';
import '../models/forecast_model.dart';

class ForecastRepositoryImpl implements ForecastRepository {
  ForecastRepositoryImpl(this.remote, this.reader);
  final ForecastRemote remote;
  final CachedReader reader;
  @override
  Future<Result<Snapshot<ForecastBundle>>> load() =>
      reader('forecast', remote.load, ForecastModel.parse);
}
