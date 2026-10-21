import '../../../../core/presentation/report_bloc.dart';
import '../../domain/entities/weekly_summary.dart';
import '../../domain/usecases/load_weekly_summary.dart';

class WeeklySummaryBloc extends ReportBloc<WeeklySummary> {
  WeeklySummaryBloc(LoadWeeklySummary super.load, [super.resets]);
}
