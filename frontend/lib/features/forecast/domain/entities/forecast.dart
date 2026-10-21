import '../../../../core/domain/amount.dart';

class ForecastDay {
  const ForecastDay(this.date, this.closing, this.sales, this.difference);
  final String date;
  final int closing, sales, difference;
}

class ForecastScenario {
  const ForecastScenario(
    this.days,
    this.shortfall,
    this.inflows,
    this.outflows,
  );
  final List<ForecastDay> days;
  final String? shortfall;
  final List<Amount> inflows, outflows;
}

class ForecastBundle {
  const ForecastBundle(
    this.asOf,
    this.scenarios,
    this.assumptions,
    this.overdue,
  );
  final String asOf;
  final Map<String, ForecastScenario> scenarios;
  final List<String> assumptions;
  final List<Amount> overdue;
}
