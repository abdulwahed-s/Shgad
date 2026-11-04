import '../../../../core/presentation/report_bloc.dart';
import '../../domain/entities/collections.dart';
import '../../domain/usecases/collections_usecases.dart';

class CollectionsBloc extends ReportBloc<Collections> {
  CollectionsBloc(
    LoadCollections super.load, [
    super.resets,
    super.changes,
    super.connectivity,
  ]);
}

class MorningBriefBloc extends ReportBloc<MorningBriefData> {
  MorningBriefBloc(
    LoadMorningBrief super.load, [
    super.resets,
    super.changes,
    super.connectivity,
  ]);
}
