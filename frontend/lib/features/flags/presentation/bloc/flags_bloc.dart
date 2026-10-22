import '../../../../core/presentation/report_bloc.dart';
import '../../domain/entities/flags.dart';
import '../../domain/usecases/load_flags.dart';

class FlagsBloc extends ReportBloc<Flags> {
  FlagsBloc(
    LoadFlags super.load, [
    super.resets,
    super.changes,
    super.connectivity,
  ]);
}
