import 'package:flutter/material.dart';
import '../domain/amount.dart';
import 'ledger_widgets.dart';

void openEvidence(BuildContext context, Amount amount) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) => EvidenceSheet(
      formula: amount.formula,
      children: [
        for (final id in amount.sources)
          Text(id, style: Theme.of(context).textTheme.bodySmall),
      ],
    ),
  );
}
