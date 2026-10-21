import '../../../../core/utils/result.dart';
import '../entities/sample_shop.dart';
import '../repositories/sample_repository.dart';

class LoadSampleShop {
  LoadSampleShop(this.repository);
  final SampleRepository repository;
  Future<Result<SampleShop>> call() => repository.load();
}

class ResetSampleShop {
  ResetSampleShop(this.repository);
  final SampleRepository repository;
  Future<Result<String>> call() => repository.reset();
}
