import '../../../../core/data/cached_reader.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/weekly_summary.dart';
import '../../domain/repositories/weekly_summary_repository.dart';
import '../datasources/weekly_summary_remote.dart';
import '../models/weekly_summary_model.dart';

class WeeklySummaryRepositoryImpl implements WeeklySummaryRepository {
  WeeklySummaryRepositoryImpl(this.remote, this.reader);
  final WeeklySummaryRemote remote;
  final CachedReader reader;
  @override
  Future<Result<Snapshot<WeeklySummary>>> load() =>
      reader('weekly_summary', remote.load, WeeklySummaryModel.parse);
}
