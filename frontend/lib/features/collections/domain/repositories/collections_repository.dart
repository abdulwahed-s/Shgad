import '../../../../core/domain/snapshot.dart';
import '../../../../core/utils/result.dart';
import '../entities/collections.dart';

abstract interface class CollectionsRepository {
  Future<Result<Snapshot<Collections>>> load();
  Future<Result<Snapshot<MorningBriefData>>> brief();
  Future<Result<CollectionDraft>> draft(String customerId, String tone);
  Future<Result<ReminderReceipt>> log(ReminderAction action);
}

abstract interface class ReminderSharingRepository {
  Future<Result<bool>> share(String text, String channel);
}
