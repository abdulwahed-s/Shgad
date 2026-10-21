import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
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
      return MerchantPage(
        title: l.closeTitle,
        actions: [
          TextButton(
            onPressed: busy ? null : () => bloc.add(OpenClose(data?.date)),
            child: Text(l.refresh),
          ),
        ],
        children: [
          if (busy) const LinearProgressIndicator(),
          if (!v.online) ...[
            InfoStrip(text: l.needsConnection),
            SecondaryButton(
              text: l.retry,
              onPressed: () => bloc.add(const RecheckClose()),
            ),
          ],
          if (state is CloseFailure)
            InfoStrip(text: failureText(l, state.failure)),
          if (data != null) ...[
            Text(l.businessDate(formatDate(data.date, l.localeName))),
            AmountView(
              amount: data.count,
              label: l.cashCount,
              hero: true,
              onTap: () => openEvidence(context, data.count),
            ),
            AmountView(
              amount: data.expected,
              label: l.expectedClose,
              onTap: () => openEvidence(context, data.expected),
            ),
            AmountView(
              amount: data.remaining,
              label: l.unexplainedDifference,
              onTap: () => openEvidence(context, data.remaining),
            ),
            InfoStrip(text: l.neutralDifference),
            Wrap(
              spacing: AppDimens.sm,
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
            Offstage(
              offstage: !v.recording,
              child: EntryPanel(
                key: ValueKey(data.date),
                lockedDate: true,
                fields: {
                  'type': 'DAILY_CASH_COUNT',
                  'business_date': data.date,
                },
                onSaved: () => bloc.add(OpenClose(data.date)),
              ),
            ),
            if (!v.recording) ...[
              const SizedBox(height: AppDimens.lg),
              if (v.saved) ...[
                InfoStrip(
                  text: v.sourceId == null
                      ? l.leftUnexplained
                      : l.savedSource(v.sourceId!),
                ),
                if (v.sourceId != null)
                  SecondaryButton(
                    text: l.evidence,
                    onPressed: () => openSourceEvidence(context, [
                      v.sourceId!,
                    ], l.savedEntryFormula),
                  ),
                if (v.sourceId != null && v.voided == null && !v.undoing)
                  SecondaryButton(
                    text: l.undo,
                    onPressed: !v.online || busy
                        ? null
                        : () => bloc.add(const BeginReviewUndo()),
                  ),
              ],
              if (v.undoing) ...[
                InfoStrip(text: l.undoNotice),
                TextFormField(
                  key: const ValueKey('review_undo_reason'),
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
              ] else ...[
                DropdownButtonFormField<String>(
                  key: ValueKey('resolution_${v.saved}'),
                  initialValue: v.choice,
                  isExpanded: true,
                  decoration: InputDecoration(labelText: l.chooseResolution),
                  items: [
                    for (final choice in resolutionChoices)
                      DropdownMenuItem(
                        value: choice,
                        child: Text(
                          resolutionText(l, choice),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: busy
                      ? null
                      : (value) {
                          if (value != null) {
                            bloc.add(ChangeResolution('choice', value));
                          }
                        },
                ),
                if (v.choice != null && v.choice != 'leave_unexplained')
                  TextFormField(
                    key: const ValueKey('resolution_amount'),
                    initialValue: v.amount,
                    decoration: InputDecoration(labelText: l.amountInput),
                    keyboardType: TextInputType.number,
                    onChanged: (value) =>
                        bloc.add(ChangeResolution('amount', value)),
                  ),
                TextFormField(
                  key: const ValueKey('resolution_note'),
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
                    style: TextStyle(
                      decoration: history.voidReason == null
                          ? null
                          : TextDecoration.lineThrough,
                    ),
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
