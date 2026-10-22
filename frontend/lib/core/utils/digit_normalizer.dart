import '../constants/data_limits.dart';

abstract final class DigitNormalizer {
  static String normalize(String input) {
    const arabic = '٠١٢٣٤٥٦٧٨٩';
    const persian = '۰۱۲۳۴۵۶۷۸۹';
    return input
        .split('')
        .map(
          (c) => arabic.contains(c)
              ? '${arabic.indexOf(c)}'
              : persian.contains(c)
              ? '${persian.indexOf(c)}'
              : c,
        )
        .join();
  }

  static int? amount(String input) {
    final text = normalize(input).trim();
    if (!RegExp(r'^[0-9]+$').hasMatch(text)) return null;
    final value = int.tryParse(text);
    // Keep web input exact; ledger validates its own bounded integer separately.
    return value != null && value > 0 && value <= DataLimits.maxExactIqd
        ? value
        : null;
  }
}
