import 'package:flutter/material.dart';
import '../domain/amount.dart';
import 'ledger_widgets.dart';

void openEvidence(BuildContext context, Amount amount) {
  openSourceEvidence(context, amount.sources, amount.formula);
}

void openSourceEvidence(
  BuildContext context,
  List<String> sources,
  String formula,
) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => EvidenceSheet(
      formula: formula,
      children: [
        for (final id in sources)
          Text(id, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );
}
