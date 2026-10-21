import '../../../../core/domain/amount.dart';
import '../../../../core/domain/review_flag.dart';

class AgedDebt {
  const AgedDebt(this.id, this.name, this.outstanding, this.days);
  final String id, name;
  final Amount outstanding;
  final int? days;
}

class WeeklySummary {
  const WeeklySummary({
    required this.start,
    required this.end,
    required this.partial,
    required this.lines,
    required this.margin,
    required this.marginShown,
    required this.coverage,
    required this.aging,
    required this.flags,
    required this.suggestion,
  });
  final String start, end, suggestion;
  final bool partial, marginShown;
  final List<Amount> lines;
  final Amount margin;
  final int? coverage;
  final List<AgedDebt> aging;
  final List<ReviewFlag> flags;
}
