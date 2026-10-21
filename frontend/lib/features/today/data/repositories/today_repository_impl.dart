import '../../../../core/data/cached_reader.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/today.dart';
import '../../domain/repositories/today_repository.dart';
import '../datasources/today_remote.dart';
import '../models/today_model.dart';

class TodayRepositoryImpl implements TodayRepository {
  TodayRepositoryImpl(this.remote, this.reader);
  final TodayRemote remote;
  final CachedReader reader;
  @override
  Future<Result<Snapshot<Today>>> load() =>
      reader('today', remote.load, TodayModel.parse);
}
