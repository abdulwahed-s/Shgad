import '../../../../core/data/cached_reader.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/flags.dart';
import '../../domain/repositories/flags_repository.dart';
import '../datasources/flags_remote.dart';
import '../models/flags_model.dart';

class FlagsRepositoryImpl implements FlagsRepository {
  FlagsRepositoryImpl(this.remote, this.reader);
  final FlagsRemote remote;
  final CachedReader reader;
  @override
  Future<Result<Snapshot<Flags>>> load() =>
      reader('flags', remote.load, FlagsModel.parse);
}
