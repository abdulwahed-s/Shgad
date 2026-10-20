import 'package:intl/intl.dart';

abstract final class IqdFormatter {
  static String digits(String input, String locale) {
    if (!locale.startsWith('ar')) return input;
    const western = '0123456789';
    const arabic = '٠١٢٣٤٥٦٧٨٩';
    return input
        .split('')
        .map((c) => western.contains(c) ? arabic[western.indexOf(c)] : c)
        .join();
  }

  static String format(
    int amount,
    String locale,
    String thousand,
    String iqd, {
    bool exact = false,
  }) {
    final abbreviated =
        !exact && amount.abs() < 1000000 && amount != 0 && amount % 1000 == 0;
    final value = abbreviated ? amount ~/ 1000 : amount;
    final number = NumberFormat.decimalPattern(locale).format(value);
    return '${digits(number, locale)} ${abbreviated ? thousand : iqd}';
  }
}
