import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../domain/amount.dart';
import 'page_header.dart';
import 'chat_bubble.dart';
import 'chat_composer.dart';
import 'focus_outline.dart';
import 'form_fields.dart';
import 'ledger_widgets.dart';
import 'section_label.dart';
import '../theme/app_theme.dart';
import '../theme/app_motion.dart';

/// Synthetic component specimens only. Never presented as a live ledger.
class GalleryPage extends StatefulWidget {
  const GalleryPage({this.initialState = 'default', super.key});
  final String initialState;
  static const specimen = Amount(
    value: 420000,
    kind: 'verified',
    label: 'cash_on_hand',
    sources: ['GALLERY-CNT'],
    formula: '',
  );
  @override
  State<GalleryPage> createState() => _GalleryPageState();
}

class _GalleryPageState extends State<GalleryPage> {
  late String selected;
  final amount = TextEditingController(text: '404500');
  final draft = TextEditingController();
  final states = WidgetStatesController();
  @override
  void initState() {
    super.initState();
    selected = widget.initialState;
    applyState();
  }

  void applyState() {
    states.value = switch (selected) {
      'hover' => {WidgetState.hovered},
      'focus' => {WidgetState.focused},
      'pressed' => {WidgetState.pressed},
      'disabled' => {WidgetState.disabled},
      _ => {},
    };
  }

  @override
  void dispose() {
    amount.dispose();
    draft.dispose();
    states.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final disabled = selected == 'disabled';
    final choices = {
      'default': l.galleryDefault,
      'hover': l.galleryHover,
      'focus': l.galleryFocus,
      'pressed': l.galleryPressed,
      'disabled': l.galleryDisabled,
      'loading': l.galleryLoading,
      'error': l.galleryError,
      'offline': l.galleryOffline,
    };
    final wide =
        MediaQuery.sizeOf(context).width >= AppDimens.expandedBreakpoint;
    final cash = GalleryPage.specimen;
    void evidence() => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      sheetAnimationStyle: const AnimationStyle(
        duration: Duration.zero,
        reverseDuration: Duration.zero,
      ),
      builder: (_) => SoftEntrance(
        child: FractionallySizedBox(
          heightFactor: .75,
          child: EvidenceSheet(
            formula: l.savedEntryFormula,
            children: [Text(cash.sources.single)],
          ),
        ),
      ),
    );
    Widget specimen(String id, String title, Widget child) => RepaintBoundary(
      key: ValueKey('gallery_$id'),
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppDimens.xl),
        child: Semantics(
          identifier: id,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SectionLabel(text: title),
              child,
            ],
          ),
        ),
      ),
    );
    final start = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        specimen(
          'hero',
          l.cashOnHand,
          HeroCard(
            amount: cash,
            label: l.cashOnHand,
            caption: l.galleryTimestamp,
            onTap: disabled ? null : evidence,
          ),
        ),
        specimen(
          'ledger',
          l.positionConfirmed,
          LedgerGroup(
            children: [
              LedgerRow(
                amount: cash,
                label: l.cashOnHand,
                onTap: disabled ? null : evidence,
              ),
              LedgerRow(
                amount: const Amount(
                  value: 404500,
                  kind: 'expected',
                  label: '',
                  sources: [],
                  formula: '',
                ),
                label: l.expectedCollections,
              ),
              LedgerRow(
                amount: const Amount(
                  value: -230000,
                  kind: 'calculated',
                  label: '',
                  sources: [],
                  formula: '',
                ),
                label: l.positionConfirmed,
              ),
              LedgerRow(
                amount: const Amount(
                  value: null,
                  kind: 'missing',
                  label: '',
                  sources: [],
                  formula: '',
                ),
                label: l.lowestCash,
              ),
            ],
          ),
        ),
        specimen(
          'pills',
          l.sourcedFigure,
          Wrap(
            spacing: AppDimens.sm,
            runSpacing: AppDimens.sm,
            children: [
              for (final kind in [
                'verified',
                'expected',
                'calculated',
                'entered',
                'missing',
                'flagged',
              ])
                StatusPill(kind: kind),
            ],
          ),
        ),
        specimen(
          'actions',
          l.reviewEntry,
          ActionGroup(
            children: [
              PrimaryButton(
                text: l.confirm,
                onPressed: disabled ? null : () {},
                statesController: states,
              ),
              SecondaryButton(
                text: l.edit,
                onPressed: disabled ? null : () {},
                statesController: states,
              ),
            ],
          ),
        ),
        specimen(
          'text_action',
          l.evidence,
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextAction(
              text: l.evidence,
              onPressed: disabled ? null : evidence,
            ),
          ),
        ),
        specimen(
          'number',
          l.columnMapping,
          Wrap(
            spacing: AppDimens.lg,
            children: const [
              NumberBadge(number: 1),
              NumberBadge(number: 2),
              NumberBadge(number: 3),
            ],
          ),
        ),
        specimen(
          'empty',
          l.noRecords,
          EmptyState(
            text: l.noRecords,
            explanation: l.chatWelcome,
            action: l.retry,
            onPressed: disabled ? null : () {},
          ),
        ),
      ],
    );
    final end = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        specimen(
          'field',
          l.amountInput,
          AmountField(
            controller: amount,
            onChanged: (_) {},
            enabled: !disabled,
          ),
        ),
        specimen(
          'date',
          l.businessDateInput,
          DateField(
            label: l.businessDateInput,
            value: '2026-09-28',
            onChanged: (_) {},
            enabled: !disabled,
          ),
        ),
        specimen(
          'choice',
          l.entryType,
          ChoiceChips(
            choices: {'cash': l.cashSale, 'credit': l.creditSale},
            selected: 'cash',
            onSelected: disabled ? null : (_) {},
          ),
        ),
        specimen(
          'segment',
          l.forecastTitle,
          SegmentedControl(
            choices: {
              'base': l.scenarioBase,
              'conservative': l.scenarioConservative,
              'stress': l.scenarioStress,
            },
            selected: 'base',
            onSelected: disabled ? null : (_) {},
          ),
        ),
        specimen(
          'strip',
          l.expected,
          InfoStrip(text: l.expectedNotice, expected: true),
        ),
        specimen(
          'error',
          l.galleryError,
          InfoStrip(text: l.errorValidation, error: true),
        ),
        specimen(
          'offline',
          l.galleryOffline,
          OfflineBanner(updatedAt: '2026-09-28T21:00:00+03:00'),
        ),
        specimen(
          'progress',
          l.checkingLedger,
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(l.checkingLedger),
              const SizedBox(height: AppDimens.sm),
              if (selected == 'loading')
                const InlineProgress()
              else
                const LinearProgressIndicator(value: .6),
            ],
          ),
        ),
        specimen(
          'chat',
          l.chatTitle,
          Column(
            children: [
              ChatBubble(text: l.galleryQuestion, merchant: true),
              const SizedBox(height: AppDimens.md),
              ChatBubble(text: l.galleryAnswer),
              const SizedBox(height: AppDimens.md),
              PromptChip(
                text: l.promptDebts,
                onPressed: disabled ? null : () {},
              ),
            ],
          ),
        ),
        specimen(
          'composer',
          l.chatInput,
          ChatComposer(
            controller: draft,
            onChanged: (_) {},
            onSubmit: disabled ? null : () {},
            enabled: !disabled,
          ),
        ),
        specimen(
          'field_error',
          l.noteInput,
          FieldLabel(
            label: l.noteInput,
            child: TextFormField(
              initialValue: l.galleryAnswer,
              enabled: !disabled,
              style: Theme.of(
                context,
              ).extension<LedgerStyles>()!.input(enabled: !disabled),
              decoration: InputDecoration(
                helperText: l.provideDetails,
                errorText: selected == 'error' ? l.errorValidation : null,
              ),
            ),
          ),
        ),
        specimen(
          'meta',
          l.updatedAt(l.galleryTimestamp),
          PageMeta(
            updated: l.updatedAt(l.galleryTimestamp),
            date: l.galleryTimestamp,
            showRefresh: true,
            onRefresh: disabled ? null : () {},
          ),
        ),
        specimen(
          'evidence',
          l.evidence,
          SizedBox(
            height: AppDimens.chartHeight * 2,
            child: EvidenceSheet(
              showHeader: true,
              closeEnabled: !disabled,
              formula: l.savedEntryFormula,
              onClose: disabled ? null : () {},
              children: [
                LedgerRow(
                  amount: cash,
                  label: l.cashOnHand,
                  exact: true,
                  voided: true,
                  caption: cash.sources.single,
                ),
                InfoStrip(text: l.voidReasonValue(l.errorAmount), error: true),
                TextAction(
                  text: l.originalRow,
                  onPressed: disabled ? null : () {},
                ),
              ],
            ),
          ),
        ),
      ],
    );
    return Theme(
      data: AppTheme.preview(Theme.of(context), states.value),
      child: InteractionPreview(
        states: states.value,
        child: Scaffold(
          appBar: PageHeader(
            title: l.galleryTitle,
            height: MediaQuery.textScalerOf(
              context,
            ).scale(AppDimens.toolbarHeight),
          ),
          body: SafeArea(
            child: Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(
                  maxWidth: AppDimens.columnsMaxWidth,
                ),
                child: ListView(
                  padding: EdgeInsets.all(wide ? AppDimens.xxl : AppDimens.lg),
                  children: [
                    Text(
                      l.gallerySpecimens,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: AppDimens.lg),
                    ledgerDropdown<String>(
                      context,
                      decoration: InputDecoration(labelText: l.galleryTitle),
                      initialValue: selected,
                      isExpanded: true,
                      items: [
                        for (final item in choices.entries)
                          DropdownMenuItem(
                            value: item.key,
                            child: Text(item.value),
                          ),
                      ],
                      onChanged: (value) {
                        if (value != null) {
                          setState(() {
                            selected = value;
                            applyState();
                          });
                        }
                      },
                    ),
                    const SizedBox(height: AppDimens.xl),
                    if (selected == 'error')
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppDimens.lg),
                        child: InfoStrip(text: l.errorValidation, error: true),
                      ),
                    if (selected == 'offline')
                      const Padding(
                        padding: EdgeInsets.only(bottom: AppDimens.lg),
                        child: OfflineBanner(
                          updatedAt: '2026-09-28T21:00:00+03:00',
                        ),
                      ),
                    if (selected == 'loading') const InlineProgress(),
                    if (wide)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(child: start),
                          const SizedBox(width: AppDimens.xl),
                          Expanded(child: end),
                        ],
                      )
                    else ...[
                      start,
                      end,
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
