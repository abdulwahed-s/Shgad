import '../../../../core/domain/snapshot.dart';
import '../../../../core/usecase/load_report.dart';
import '../../../../core/utils/result.dart';
import '../entities/debts.dart';
import '../repositories/debts_repository.dart';

class LoadDebts extends LoadReport<Debts> {
  LoadDebts(this.repository);
  final DebtsRepository repository;
  @override
  Future<Result<Snapshot<Debts>>> call() => repository.load();
}
