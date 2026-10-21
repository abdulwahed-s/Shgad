import '../../domain/entities/sample_shop.dart';

class SampleModel {
  static SampleShop parse(Map<String, dynamic> j) => SampleShop(
    j['business_as_of'] as String,
    j['data_version'] as String,
    j['llm_available'] as bool,
  );
  static String reset(Map<String, dynamic> j) {
    if (j['ok'] != true) throw const FormatException('Reset was not confirmed');
    return j['data_version'] as String;
  }
}
