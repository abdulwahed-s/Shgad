import '../../../../core/domain/snapshot.dart';
import '../../../../core/usecase/load_report.dart';
import '../../../../core/utils/result.dart';
import '../entities/flags.dart';
import '../repositories/flags_repository.dart';

class LoadFlags extends LoadReport<Flags> {
  LoadFlags(this.repository);
  final FlagsRepository repository;
  @override
  Future<Result<Snapshot<Flags>>> call() => repository.load();
}
