import '../domain/snapshot.dart';
import '../utils/result.dart';

abstract class LoadReport<T> {
  Future<Result<Snapshot<T>>> call();
}
