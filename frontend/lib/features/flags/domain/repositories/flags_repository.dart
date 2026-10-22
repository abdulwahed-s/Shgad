import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../entities/flags.dart';

abstract interface class FlagsRepository {
  Future<Result<Snapshot<Flags>>> load();
}
