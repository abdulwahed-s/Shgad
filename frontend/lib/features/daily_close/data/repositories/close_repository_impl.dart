import '../../../../core/error/app_failure.dart';
import '../../../../core/domain/session_events.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/daily_close.dart';
import '../../domain/repositories/close_repository.dart';
import '../datasources/close_remote.dart';
import '../models/close_model.dart';

class CloseRepositoryImpl implements CloseRepository {
  CloseRepositoryImpl(this.remote, [this.events]);
  final CloseRemote remote;
  final SessionEvents? events;
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
  Future<Result<DailyClose>> load(String? date) =>
      _result(() async => CloseModel.parse(await remote.load(date)));
  @override
  Future<Result<ResolutionSaved>> resolve(ResolutionDraft draft) =>
      _result(() async {
        final receipt = CloseModel.saved(
          await remote.resolve(draft.date, CloseModel.payload(draft)),
        );
        events?.changed();
        return receipt;
      });
}
