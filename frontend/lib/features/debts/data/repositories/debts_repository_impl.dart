import '../../../../core/data/cached_reader.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/debts.dart';
import '../../domain/repositories/debts_repository.dart';
import '../datasources/debts_remote.dart';
import '../models/debts_model.dart';

class DebtsRepositoryImpl implements DebtsRepository {
  DebtsRepositoryImpl(this.remote, this.reader);
  final DebtsRemote remote;
  final CachedReader reader;
  @override
  Future<Result<Snapshot<Debts>>> load() =>
      reader('debts', remote.load, DebtsModel.parse);
}
