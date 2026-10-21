import '../cache/response_cache.dart';
import '../domain/snapshot.dart';
import '../domain/session_events.dart';
import '../error/app_failure.dart';
import '../network/api_client.dart';
import '../utils/result.dart';

class CachedReader {
  CachedReader(this.cache, [this.events]);
  final ResponseCache cache;
  final SessionEvents? events;
  Future<Result<Snapshot<T>>> call<T>(
    String key,
    Future<Map<String, dynamic>> Function() request,
    T Function(Map<String, dynamic>) parse,
  ) async {
    final generation = events?.generation;
    try {
      final json = await request();
      if (generation != events?.generation) {
        return const Failed(AppFailure(FailureKind.unavailable));
      }
      final data = parse(json);
      final stamp =
          json['last_synced_at'] as String? ??
          DateTime.now().toUtc().toIso8601String();
      await cache.write(key, CacheRecord(json, stamp));
      return Success(Snapshot(data, stamp));
    } on ApiException catch (e) {
      if (e.failure.kind == FailureKind.offline) {
        final record = await cache.read(key);
        if (record != null) {
          try {
            return Success(
              Snapshot(parse(record.json), record.updatedAt, offline: true),
            );
          } catch (_) {
            /* Invalid cache is never turned into financial data. */
          }
        }
      }
      return Failed(e.failure);
    } catch (_) {
      return const Failed(AppFailure(FailureKind.internal));
    }
  }
}
