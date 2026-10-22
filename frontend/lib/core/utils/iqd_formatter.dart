/// String grouping preserves every integer digit, including near the web limit.
abstract final class IqdFormatter {
  static String digits(String input, String locale) {
    if (!locale.startsWith('ar')) return input;
    const western = '0123456789', arabic = '٠١٢٣٤٥٦٧٨٩';
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
    final raw = value.toString();
    final negative = raw.startsWith('-');
    final magnitude = negative ? raw.substring(1) : raw;
    final text = StringBuffer();
    final separator = locale.startsWith('ar') ? '٬' : ',';
    if (negative) text.write('-');
    for (var i = 0; i < magnitude.length; i++) {
      if (i > 0 && (magnitude.length - i) % 3 == 0) text.write(separator);
      text.write(magnitude[i]);
    }
    return '${digits(text.toString(), locale)} ${abbreviated ? thousand : iqd}';
  }
}
