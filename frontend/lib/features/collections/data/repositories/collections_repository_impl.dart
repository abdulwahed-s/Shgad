import '../../../../core/data/cached_reader.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/collections.dart';
import '../../domain/repositories/collections_repository.dart';
import '../datasources/collections_remote.dart';
import '../models/collections_model.dart';

class CollectionsRepositoryImpl implements CollectionsRepository {
  CollectionsRepositoryImpl(this.remote, this.reader);
  final CollectionsRemote remote;
  final CachedReader reader;
  @override
  Future<Result<Snapshot<Collections>>> load() =>
      reader('collections', remote.load, CollectionsModel.collections);
  @override
  Future<Result<Snapshot<MorningBriefData>>> brief() =>
      reader('brief', remote.brief, CollectionsModel.brief);
  Future<Result<T>> _result<T>(Future<T> Function() action) async {
    try {
      return Success(await action());
    } on ApiException catch (e) {
      return Failed(e.failure);
    } catch (e) {
      return Failed(dataFailure(e));
    }
  }

  @override
  Future<Result<CollectionDraft>> draft(String customerId, String tone) =>
      _result(
        () async =>
            CollectionsModel.draft(await remote.draft(customerId, tone)),
      );
  @override
  Future<Result<ReminderReceipt>> log(ReminderAction action) => _result(
    () async => CollectionsModel.receipt(
      await remote.log({
        'counterparty_id': action.customerId,
        'tone': action.tone,
        'channel': action.channel,
        'edited': action.edited,
      }),
    ),
  );
}
