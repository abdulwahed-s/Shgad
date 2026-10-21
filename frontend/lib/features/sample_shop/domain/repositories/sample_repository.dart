import '../../../../core/utils/result.dart';
import '../entities/sample_shop.dart';

abstract interface class SampleRepository {
  Future<Result<SampleShop>> load();
  Future<Result<String>> reset();
}
