import 'package:intl/intl.dart';
import 'iqd_formatter.dart';

/// Display conversion only. Business dates always come from the server.
String formatDate(String value, String locale, {bool timestamp = false}) {
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  final date = timestamp
      ? parsed.toUtc().add(const Duration(hours: 3))
      : parsed;
  return IqdFormatter.digits(
    DateFormat(
      timestamp ? 'yyyy/MM/dd · HH:mm' : 'yyyy/MM/dd',
      locale,
    ).format(date),
    locale,
  );
}
