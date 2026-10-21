import 'amount.dart';

class ReviewFlag {
  const ReviewFlag(
    this.id,
    this.type,
    this.reason,
    this.amount,
    this.sources,
    this.basis,
    this.nextStep,
  );
  final String id, type, reason, basis, nextStep;
  final Amount amount;
  final List<String> sources;
}
