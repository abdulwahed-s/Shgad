import 'package:flutter/material.dart';
import '../domain/known_zero_query.dart';
import '../utils/date_formatter.dart';
import '../utils/iqd_formatter.dart';
import '../../l10n/generated/app_localizations.dart';
import 'ledger_widgets.dart';

/// Display the server's evidence unchanged using already approved copy.
class KnownZeroEvidence extends StatelessWidget {
  const KnownZeroEvidence({required this.query, super.key});
  final KnownZeroQuery query;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          l.resolvedPeriod(
            formatDate(query.start, l.localeName),
            formatDate(query.end, l.localeName),
          ),
        ),
        InfoStrip(text: l.noEvidenceRows),
        Text(
          l.metricValue(
            IqdFormatter.digits(query.matchingRows.toString(), l.localeName),
            l.countUnit,
          ),
        ),
        ExpansionTile(
          title: Text(l.originalFormula),
          children: [
            SelectableCaption(
              query.originalQuery,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ],
    );
  }
}
