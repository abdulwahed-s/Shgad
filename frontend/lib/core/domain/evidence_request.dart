import 'known_zero_query.dart';

class EvidenceRequest {
  const EvidenceRequest(this.sources, this.formula, {this.queryEvidence});
  final List<String> sources;
  final String formula;
  final KnownZeroQuery? queryEvidence;
}
