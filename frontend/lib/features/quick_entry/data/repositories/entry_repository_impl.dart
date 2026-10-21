import '../../../../core/error/app_failure.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/entry.dart';
import '../../domain/repositories/entry_repository.dart';
import '../datasources/entry_remote.dart';
import '../models/entry_model.dart';

class EntryRepositoryImpl implements EntryRepository {
  EntryRepositoryImpl(this.remote);
  final EntryRemote remote;
  Future<Result<T>> _result<T>(Future<T> Function() action) async {
    try {
      return Success(await action());
    } on ApiException catch (e) {
      return Failed(e.failure);
    } catch (_) {
      return const Failed(AppFailure(FailureKind.internal));
    }
  }

  @override
  Future<Result<EntrySetup>> setup() =>
      _result(() async => EntryModel.setup(await remote.setup()));
  @override
  Future<Result<SavedEntry>> save(EntryDraft draft) => _result(
    () async =>
        EntryModel.receipt(await remote.save(EntryModel.payload(draft))),
  );
  @override
  Future<Result<VoidedEntry>> undo(
    String sourceId,
    String clientId,
    String reason,
  ) => _result(
    () async => EntryModel.voided(
      await remote.undo(sourceId, {
        'client_entry_id': clientId,
        'reason': reason,
      }),
    ),
  );
}
