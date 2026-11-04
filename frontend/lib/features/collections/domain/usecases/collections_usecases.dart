import '../../../../core/domain/snapshot.dart';
import '../../../../core/usecase/load_report.dart';
import '../../../../core/utils/result.dart';
import '../entities/collections.dart';
import '../repositories/collections_repository.dart';

class LoadCollections extends LoadReport<Collections> {
  LoadCollections(this.repository);
  final CollectionsRepository repository;
  @override
  Future<Result<Snapshot<Collections>>> call() => repository.load();
}

class LoadMorningBrief extends LoadReport<MorningBriefData> {
  LoadMorningBrief(this.repository);
  final CollectionsRepository repository;
  @override
  Future<Result<Snapshot<MorningBriefData>>> call() => repository.brief();
}

class MakeReminderDraft {
  MakeReminderDraft(this.repository);
  final CollectionsRepository repository;
  Future<Result<CollectionDraft>> call(String customerId, String tone) =>
      repository.draft(customerId, tone);
}

class ShareReminderText {
  ShareReminderText(this.repository);
  final ReminderSharingRepository repository;
  Future<Result<bool>> call(String text, String channel) =>
      repository.share(text, channel);
}

class LogReminder {
  LogReminder(this.repository);
  final CollectionsRepository repository;
  Future<Result<ReminderReceipt>> call(ReminderAction action) =>
      repository.log(action);
}
