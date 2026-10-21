import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/domain/evidence_request.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../../quick_entry/presentation/pages/entry_page.dart';
import '../../domain/entities/source_record.dart';
import '../bloc/evidence_bloc.dart';

class EvidencePage extends StatelessWidget {
  const EvidencePage({required this.request, super.key});
  final EvidenceRequest request;
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<EvidenceBloc>()..add(OpenEvidence(request)),
    child: const _EvidenceView(),
  );
}

class _EvidenceView extends StatelessWidget {
  const _EvidenceView();
  @override
  Widget build(BuildContext context) =>
      BlocBuilder<EvidenceBloc, EvidenceState>(
        builder: (context, state) {
          final l = AppLocalizations.of(context);
          final v = state.view;
          final bloc = context.read<EvidenceBloc>();
          final busy = state is EvidenceLoading;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.all(AppDimens.lg),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        l.evidence,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    IconButton(
                      tooltip: l.dismiss,
                      onPressed: () => context.pop(),
                      icon: const Icon(Icons.close_outlined),
                    ),
                  ],
                ),
              ),
              if (busy) const LinearProgressIndicator(),
              Expanded(
                child: EvidenceSheet(
                  formula: v.request.formula,
                  children: [
                    if (!v.online) ...[
                      InfoStrip(text: l.needsConnection),
                      SecondaryButton(
                        text: l.retry,
                        onPressed: () => bloc.add(const RecheckEvidence()),
                      ),
                    ],
                    if (state is EvidenceFailure)
                      FailureView(
                        failure: state.failure,
                        onRetry: () => bloc.add(OpenEvidence(v.request)),
                      ),
                    if (v.records.isEmpty && !busy && state is EvidenceLoaded)
                      InfoStrip(text: l.noEvidenceRows),
                    if (v.voided != null)
                      InfoStrip(
                        text: l.voidSaved(v.voided!.voidId, v.voided!.reason),
                      ),
                    for (final record in v.records) ...[
                      const Divider(),
                      Text(
                        record.id,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          decoration: record.row?.status == 'voided'
                              ? TextDecoration.lineThrough
                              : null,
                        ),
                      ),
                      if (record.row != null)
                        EvidenceLedgerRow(
                          row: v.details[record.id] ?? record.row!,
                          online: v.online,
                          busy: busy,
                        ),
                      if (record.opening != null) ...[
                        Text(
                          l.businessDate(
                            formatDate(record.date!, l.localeName),
                          ),
                        ),
                        AmountView(
                          amount: record.opening!,
                          label: l.openingBalance,
                          exact: true,
                        ),
                        SelectableText(
                          record.rawText,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                      if (record.buy != null) ...[
                        Text(record.name!),
                        AmountView(
                          amount: record.buy!,
                          label: l.unitBuyPrice,
                          exact: true,
                        ),
                        AmountView(
                          amount: record.sell!,
                          label: l.unitSellPrice,
                          exact: true,
                        ),
                        SelectableText(
                          record.rawText,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ],
                    if (v.voidSource != null) ...[
                      InfoStrip(text: l.undoNotice),
                      Text(l.savedSource(v.voidSource!)),
                      TextFormField(
                        key: ValueKey('void_reason_${v.voidSource}'),
                        initialValue: v.reason,
                        decoration: InputDecoration(labelText: l.voidReason),
                        onChanged: (value) =>
                            bloc.add(ChangeSourceReason(value)),
                      ),
                      PrimaryButton(
                        text: l.confirmUndo,
                        onPressed: !v.online || busy
                            ? null
                            : () => bloc.add(const ConfirmSourceVoid()),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          );
        },
      );
}

class EvidenceLedgerRow extends StatelessWidget {
  const EvidenceLedgerRow({
    required this.row,
    required this.online,
    required this.busy,
    super.key,
  });
  final LedgerRow row;
  final bool online, busy;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final bloc = context.read<EvidenceBloc>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(l.businessDate(formatDate(row.date, l.localeName))),
        AmountView(
          amount: row.amount,
          label: entryTypeText(l, row.type),
          exact: true,
          voided: row.status == 'voided',
        ),
        if (row.partyName != null)
          Text(l.partyOption(row.partyName!, row.partyId!)),
        if (row.obligationId != null)
          Text(l.obligationReference(row.obligationId!)),
        if (row.description.isNotEmpty) Text(row.description),
        if (row.voidReason != null) ...[
          InfoStrip(text: l.voidReasonValue(row.voidReason!)),
          Text(row.voidId!),
          Text(
            l.timeInBaghdad(
              formatDate(row.voidedAt!, l.localeName, timestamp: true),
            ),
          ),
          SecondaryButton(
            text: l.correctEntry,
            onPressed: !online || busy
                ? null
                : () => context.push(
                    Uri(
                      path: '/entry',
                      queryParameters: bloc.correctionFields(row),
                    ).toString(),
                  ),
          ),
        ],
        if (row.correctionOf != null)
          SecondaryButton(
            text: l.correctionOf(row.correctionOf!),
            onPressed: () => openSourceEvidence(context, [
              row.correctionOf!,
            ], l.savedEntryFormula),
          ),
        if (row.rawText.isEmpty)
          SecondaryButton(
            text: l.originalRow,
            onPressed: !online || busy
                ? null
                : () => bloc.add(OpenSourceDetail(row.id)),
          )
        else
          SelectableText(
            row.rawText,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        if (row.status != 'voided')
          SecondaryButton(
            text: l.undo,
            onPressed: !online || busy
                ? null
                : () => bloc.add(BeginSourceVoid(row.id)),
          ),
      ],
    );
  }
}
