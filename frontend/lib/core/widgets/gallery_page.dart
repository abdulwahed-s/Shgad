import 'merchant_app_bar.dart';
import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../domain/amount.dart';
import 'chat_bubble.dart';
import 'ledger_widgets.dart';
import 'section_label.dart';

/// Isolated component specimens, never shown as live merchant data.
class GalleryPage extends StatelessWidget {
  const GalleryPage({super.key});
  static const specimen = Amount(
    value: 420000,
    kind: 'verified',
    label: 'cash_on_hand',
    sources: ['GALLERY-CNT'],
    formula: 'latest DAILY_CASH_COUNT',
  );
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      appBar: merchantAppBar(context, l.galleryTitle, menu: false),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppDimens.contentMaxWidth,
          ),
          child: ListView(
            padding: const EdgeInsets.all(AppDimens.lg),
            children: [
              SectionLabel(text: l.gallerySpecimens),
              LedgerCard(
                child: AmountView(
                  amount: specimen,
                  label: l.cashOnHand,
                  hero: true,
                  caption: l.galleryTimestamp,
                  onTap: () => showModalBottomSheet<void>(
                    context: context,
                    builder: (_) => EvidenceSheet(
                      formula: specimen.formula,
                      children: [Text(specimen.sources.single)],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppDimens.lg),
              Wrap(
                spacing: AppDimens.sm,
                runSpacing: AppDimens.sm,
                children: const [
                  StatusLabel(kind: 'verified'),
                  StatusLabel(kind: 'calculated'),
                  StatusLabel(kind: 'expected'),
                  StatusLabel(kind: 'missing'),
                  StatusLabel(kind: 'flagged'),
                ],
              ),
              AmountView(
                amount: const Amount(
                  value: -230000,
                  kind: 'calculated',
                  label: 'position_confirmed',
                  sources: [],
                  formula: '',
                ),
                label: l.positionConfirmed,
              ),
              InfoStrip(text: l.expectedNotice, expected: true),
              const SizedBox(height: AppDimens.lg),
              ChatBubble(text: l.galleryQuestion, merchant: true),
              const SizedBox(height: AppDimens.sm),
              ChatBubble(text: l.galleryAnswer),
              PromptChip(text: l.galleryQuestion, onPressed: () {}),
              OfflineBanner(updatedAt: l.galleryTimestamp),
              const SizedBox(height: AppDimens.lg),
              PrimaryButton(text: l.confirm, onPressed: () {}),
              SecondaryButton(text: l.evidence, onPressed: () {}),
              EmptyState(text: l.noRecords, action: l.retry, onPressed: () {}),
              const Align(
                alignment: AlignmentDirectional.centerStart,
                child: NumberBadge(number: 1),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
