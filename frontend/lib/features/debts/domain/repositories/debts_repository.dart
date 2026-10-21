import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../entities/debts.dart';

abstract interface class DebtsRepository {
  Future<Result<Snapshot<Debts>>> load();
}
