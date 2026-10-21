import '../../../../core/presentation/report_bloc.dart';
import '../../domain/entities/today.dart';
import '../../domain/usecases/load_today.dart';

class TodayBloc extends ReportBloc<Today> {
  TodayBloc(LoadToday super.load, [super.resets]);
}
