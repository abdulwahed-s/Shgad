import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../domain/amount.dart';
import '../domain/evidence_request.dart';

void openEvidence(BuildContext context, Amount amount) => context.push(
  '/evidence',
  extra: EvidenceRequest(
    amount.sources,
    amount.formula,
    queryEvidence: amount.queryEvidence,
  ),
);
void openSourceEvidence(
  BuildContext context,
  List<String> sources,
  String formula,
) {
  context.push('/evidence', extra: EvidenceRequest(sources, formula));
}
