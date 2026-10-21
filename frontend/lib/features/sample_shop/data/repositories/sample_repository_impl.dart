import '../../../../core/cache/response_cache.dart';
import '../../../../core/domain/session_events.dart';
import '../../../../core/error/app_failure.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/utils/result.dart';
import '../../domain/entities/sample_shop.dart';
import '../../domain/repositories/sample_repository.dart';
import '../datasources/sample_remote.dart';
import '../models/sample_model.dart';

class SampleRepositoryImpl implements SampleRepository {
  SampleRepositoryImpl(this.remote, this.cache, this.events);
  final SampleRemote remote;
  final ResponseCache cache;
  final SessionEvents events;
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
  Future<Result<SampleShop>> load() =>
      _result(() async => SampleModel.parse(await remote.load()));
  @override
  Future<Result<String>> reset() => _result(() async {
    final version = SampleModel.reset(await remote.reset());
    await cache.clear();
    events.reset();
    return version;
  });
}
