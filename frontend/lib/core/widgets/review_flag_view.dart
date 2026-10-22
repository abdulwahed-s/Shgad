import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../domain/review_flag.dart';
import 'ledger_widgets.dart';
import 'open_evidence.dart';

String flagTitle(AppLocalizations l, String type) => switch (type) {
  'unmatched' => l.flagUnmatched,
  'suspected_duplicate' => l.flagDuplicate,
  'partially_paid' => l.flagPartial,
  'overdue' => l.flagOverdue,
  _ => l.flagAmbiguous,
};
String flagBasis(AppLocalizations l, String basis) => switch (basis) {
  'definite' || 'strong' => l.basisVerified,
  'same_amount_party_day' => l.basisSameDay,
  'verified_partial_allocations' => l.basisPartial,
  'due_date_before_business_as_of' => l.basisOverdue,
  'unmatched' => l.basisUnmatched,
  _ => l.basisCandidate,
};
String flagReason(AppLocalizations l, String reason, String type) =>
    switch (reason) {
      'origin_voided' => l.flagOriginVoided,
      'unallocated_payment' => l.flagUnallocated,
      'ambiguous_obligations' => l.reasonAmbiguous,
      'similar_name_only' => l.reasonSimilarName,
      'payment_exceeds_outstanding' => l.reasonExceeds,
      'missing_due_date' => l.reasonDueMissing,
      'outside_due_window' => l.reasonDueWindow,
      _ => flagTitle(l, type),
    };

class ReviewFlagView extends StatelessWidget {
  const ReviewFlagView({required this.flag, super.key});
  final ReviewFlag flag;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(),
        AmountView(
          amount: flag.amount,
          label: flagTitle(l, flag.type),
          onTap: () => openEvidence(context, flag.amount),
        ),
        Text(flagReason(l, flag.reason, flag.type)),
        Text(flagBasis(l, flag.basis)),
        Text(
          flag.nextStep == 'provide_details' ? l.provideDetails : l.flagReview,
        ),
        Text(flag.id, style: Theme.of(context).textTheme.bodySmall),
        SecondaryButton(
          text: l.evidence,
          onPressed: () =>
              openSourceEvidence(context, flag.sources, flag.amount.formula),
        ),
      ],
    );
  }
}
