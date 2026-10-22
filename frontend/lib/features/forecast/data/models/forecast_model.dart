import '../../../../core/data/amount_model.dart';
import '../../domain/entities/forecast.dart';

class ForecastModel {
  static ForecastBundle parse(Map<String, dynamic> j) {
    final scenarios = <String, ForecastScenario>{};
    for (final name in ['base', 'conservative', 'stress']) {
      final s = j['scenarios'][name];
      final days = (s['days'] as List)
          .map(
            (d) => ForecastDay(
              d['date'] as String,
              readRequiredIqd(d['closing_iqd']),
              readRequiredIqd(d['cash_sales_iqd']),
              readRequiredIqd(d['unlinked_cash_iqd']),
            ),
          )
          .toList();
      if (days.length != 30 || days.map((d) => d.date).toSet().length != 30) {
        throw const FormatException('Forecast horizon');
      }
      scenarios[name] = ForecastScenario(
        days,
        s['first_shortfall_date'] as String?,
        (s['top_inflows'] as List)
            .map((d) => parseAmount(d['amount']))
            .toList(),
        (s['top_outflows'] as List)
            .map((d) => parseAmount(d['amount']))
            .toList(),
      );
    }
    return ForecastBundle(
      j['as_of'] as String,
      scenarios,
      List<String>.from(j['assumption_keys'] as List),
      (j['overdue_excluded'] as List)
          .map((d) => parseAmount(d['outstanding']))
          .toList(),
    );
  }
}
