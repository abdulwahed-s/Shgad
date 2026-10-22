import '../../../../core/data/flag_model.dart';
import '../../domain/entities/flags.dart';

class FlagsModel {
  static Flags parse(Map<String, dynamic> j) =>
      Flags((j['items'] as List).map(parseFlag).toList());
}
