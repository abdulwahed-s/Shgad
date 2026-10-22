import '../../../../core/presentation/report_bloc.dart';
import '../../domain/entities/debts.dart';
import '../../domain/usecases/load_debts.dart';

class DebtsBloc extends ReportBloc<Debts> {
  DebtsBloc(
    LoadDebts super.load, [
    super.resets,
    super.changes,
    super.connectivity,
  ]);
}
