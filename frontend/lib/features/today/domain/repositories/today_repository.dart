import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../entities/today.dart';

abstract interface class TodayRepository {
  Future<Result<Snapshot<Today>>> load();
}
