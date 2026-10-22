import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/page_header.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../../quick_entry/presentation/pages/entry_page.dart';
import '../bloc/close_bloc.dart';

String resolutionText(AppLocalizations l, String choice) => switch (choice) {
  'leave_unexplained' => l.leaveUnexplained,
  'cash_sale_unitemized' => l.reviewCashSale,
  'capital_injection' => l.capitalInjection,
  'expense_unrecorded' => l.reviewExpense,
  'owner_drawing_unrecorded' => l.reviewDrawing,
  _ => l.chooseResolution,
};

class ClosePage extends StatelessWidget {
  const ClosePage({this.date, super.key});
  final String? date;
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<CloseBloc>()..add(OpenClose(date)),
    child: const _CloseView(),
  );
}

class _CloseView extends StatelessWidget {
  const _CloseView();
  @override
  Widget build(BuildContext context) => BlocBuilder<CloseBloc, CloseState>(
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final v = state.view;
      final data = v.data;
      final bloc = context.read<CloseBloc>();
      final busy = state is CloseLoading;
      final hideCountPanel = !v.recording && data?.count.value != null;
      return MerchantPage(
        title: l.closeTitle,
        children: [
          if (busy) const LinearProgressIndicator(),
          if (!v.online) ...[
            InfoStrip(text: l.needsConnection, offline: true),
            TextAction(
              text: l.retry,
              onPressed: () => bloc.add(const RecheckClose()),
            ),
          ],
          if (state is CloseFailure)
            InfoStrip(text: failureText(l, state.failure), error: true),
          if (data != null) ...[
            PageMeta(
              date: l.businessDate(formatDate(data.date, l.localeName)),
              onRefresh: busy ? null : () => bloc.add(OpenClose(data.date)),
            ),
            Offstage(
              key: ValueKey('close_entry_${data.date}'),
              offstage: hideCountPanel,
              child: ExcludeFocus(
                excluding: hideCountPanel,
                child: TickerMode(
                  enabled: !hideCountPanel,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: AppDimens.xl),
                    child: EntryPanel(
                      amountFirst: true,
                      key: ValueKey(data.date),
                      lockedDate: true,
                      fields: {
                        'type': 'DAILY_CASH_COUNT',
                        'business_date': data.date,
                      },
                      onSaved: () => bloc
                        ..add(const ChooseClosePanel(true))
                        ..add(OpenClose(data.date)),
                      onVoided: () => bloc
                        ..add(const ChooseClosePanel(true))
                        ..add(OpenClose(data.date)),
                    ),
                  ),
                ),
              ),
            ),
            LedgerGroup(
              children: [
                AmountView(
                  amount: data.count,
                  label: l.cashCount,
                  hero: true,
                  onTap: () => openEvidence(context, data.count),
                ),
                LedgerRow(
                  amount: data.expected,
                  label: l.expectedClose,
                  onTap: () => openEvidence(context, data.expected),
                ),
                LedgerRow(
                  amount: data.remaining,
                  label: l.unexplainedDifference,
                  onTap: () => openEvidence(context, data.remaining),
                ),
              ],
            ),
            const SizedBox(height: AppDimens.lg),
            InfoStrip(text: l.neutralDifference),
            const SizedBox(height: AppDimens.md),
            ActionGroup(
              children: [
                SecondaryButton(
                  text: l.recordCloseEntries,
                  onPressed: () => bloc.add(const ChooseClosePanel(true)),
                ),
                SecondaryButton(
                  text: l.reviewDifference,
                  onPressed: () => bloc.add(const ChooseClosePanel(false)),
                ),
              ],
            ),
            if (!v.recording && data.count.value != null) ...[
              const SizedBox(height: AppDimens.lg),
              if (v.saved) ...[
                InfoStrip(
                  text: v.sourceId == null
                      ? l.leftUnexplained
                      : l.savedSource(v.sourceId!),
                ),
                if (v.sourceId != null) ...[
                  const SizedBox(height: AppDimens.md),
                  ActionGroup(
                    children: [
                      SecondaryButton(
                        text: l.evidence,
                        onPressed: () => openSourceEvidence(context, [
                          v.sourceId!,
                        ], l.savedEntryFormula),
                      ),
                      if (v.voided == null && !v.undoing)
                        SecondaryButton(
                          text: l.undo,
                          onPressed: !v.online || busy
                              ? null
                              : () => bloc.add(const BeginReviewUndo()),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: AppDimens.md),
              ],
              if (v.undoing) ...[
                InfoStrip(text: l.undoNotice),
                const SizedBox(height: AppDimens.md),
                ledgerTextField(
                  context,
                  key: const ValueKey('review_undo_reason'),
                  enabled: !busy,
                  initialValue: v.reason,
                  decoration: InputDecoration(labelText: l.voidReason),
                  onChanged: (value) => bloc.add(ChangeReviewReason(value)),
                ),
                PrimaryButton(
                  text: l.confirmUndo,
                  onPressed: !v.online || busy
                      ? null
                      : () => bloc.add(const ConfirmReviewUndo()),
                ),
              ] else if (v.voided != null)
                InfoStrip(text: l.voidSaved(v.voided!.voidId, v.voided!.reason))
              else if (v.confirm) ...[
                LedgerCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        l.resolutionConfirmation(
                          resolutionText(l, v.choice!),
                          formatDate(data.date, l.localeName),
                        ),
                      ),
                      if (v.choice != 'leave_unexplained' && v.entered != null)
                        AmountView(
                          amount: v.entered!,
                          label: l.amountInput,
                          exact: true,
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: AppDimens.md),
                ActionGroup(
                  children: [
                    PrimaryButton(
                      key: const ValueKey('resolution_save'),
                      text: l.confirm,
                      onPressed: !v.online || busy
                          ? null
                          : () => bloc.add(const ConfirmResolution()),
                    ),
                    SecondaryButton(
                      text: l.edit,
                      onPressed: busy
                          ? null
                          : () => bloc.add(const EditResolution()),
                    ),
                  ],
                ),
              ] else ...[
                Text(
                  l.chooseResolution,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
                RadioGroup<String>(
                  key: ValueKey('resolution_${v.saved}'),
                  groupValue: v.choice,
                  onChanged: (value) {
                    if (value != null && !busy) {
                      bloc.add(ChangeResolution('choice', value));
                    }
                  },
                  child: Column(
                    children: [
                      for (final choice in resolutionChoices)
                        RadioListTile<String>(
                          value: choice,
                          enabled: !busy,
                          title: Text(resolutionText(l, choice)),
                        ),
                    ],
                  ),
                ),
                if (v.choice != null && v.choice != 'leave_unexplained')
                  ledgerTextField(
                    context,
                    key: const ValueKey('resolution_amount'),
                    enabled: !busy,
                    initialValue: v.amount,
                    decoration: InputDecoration(labelText: l.amountInput),
                    keyboardType: TextInputType.number,
                    onChanged: (value) =>
                        bloc.add(ChangeResolution('amount', value)),
                  ),
                ledgerTextField(
                  context,
                  key: const ValueKey('resolution_note'),
                  enabled: !busy,
                  initialValue: v.note,
                  decoration: InputDecoration(labelText: l.noteInput),
                  onChanged: (value) =>
                      bloc.add(ChangeResolution('note', value)),
                ),
                const SizedBox(height: AppDimens.lg),
                PrimaryButton(
                  text: l.reviewEntry,
                  onPressed: !v.online || busy
                      ? null
                      : () => bloc.add(const PrepareResolution()),
                ),
              ],
            ],
            const SizedBox(height: AppDimens.xl),
            AmountView(
              amount: data.previous,
              label: l.previousCount,
              onTap: () => openEvidence(context, data.previous),
            ),
            for (final history in data.history) ...[
              Text(resolutionText(l, history.resolution)),
              if (history.sourceId != null)
                TextButton(
                  onPressed: () => openSourceEvidence(context, [
                    history.sourceId!,
                  ], l.savedEntryFormula),
                  child: Text(
                    history.sourceId!,
                    style: history.voidReason == null
                        ? Theme.of(context).textTheme.bodySmall
                        : Theme.of(
                            context,
                          ).extension<LedgerStyles>()!.struckCaption,
                  ),
                ),
              if (history.voidReason != null)
                Text(l.voidReasonValue(history.voidReason!)),
              if (history.note != null) Text(history.note!),
            ],
          ],
        ],
      );
    },
  );
}
