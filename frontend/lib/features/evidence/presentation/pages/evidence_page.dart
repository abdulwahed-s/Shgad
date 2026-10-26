import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/domain/evidence_request.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/known_zero_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../../../core/widgets/entry_type_text.dart';
import '../../domain/entities/source_record.dart' as source;
import '../bloc/evidence_bloc.dart';

class EvidencePage extends StatelessWidget {
  const EvidencePage({required this.request, this.controller, super.key});
  final EvidenceRequest request;
  final ScrollController? controller;
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<EvidenceBloc>()..add(OpenEvidence(request)),
    child: _EvidenceView(controller: controller),
  );
}

class _EvidenceView extends StatelessWidget {
  const _EvidenceView({this.controller});
  final ScrollController? controller;
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
              if (busy) const LinearProgressIndicator(),
              Expanded(
                child: EvidenceSheet(
                  showHeader: true,
                  controller: controller,
                  formula: v.request.formula,
                  children: [
                    if (!v.online) ...[
                      InfoStrip(text: l.needsConnection),
                      TextAction(
                        text: l.retry,
                        onPressed: () => bloc.add(const RecheckEvidence()),
                      ),
                    ],
                    if (state is EvidenceFailure)
                      FailureView(
                        failure: state.failure,
                        onRetry: () => bloc.add(OpenEvidence(v.request)),
                      ),
                    if (v.request.queryEvidence != null)
                      KnownZeroEvidence(query: v.request.queryEvidence!),
                    if (v.request.queryEvidence == null &&
                        v.records.isEmpty &&
                        !busy &&
                        state is EvidenceLoaded)
                      InfoStrip(text: l.noEvidenceRows),
                    if (v.voided != null)
                      InfoStrip(
                        text: l.voidSaved(v.voided!.voidId, v.voided!.reason),
                      ),
                    for (final record in v.records) ...[
                      const Divider(),
                      SelectableCaption(
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
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        AmountView(
                          amount: record.opening!,
                          label: l.openingBalance,
                          exact: true,
                        ),
                        SelectableCaption(
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
                        SelectableCaption(
                          record.rawText,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ],
                    if (v.voidSource != null) ...[
                      InfoStrip(text: l.undoNotice),
                      Text(l.savedSource(v.voidSource!)),
                      ledgerTextField(
                        context,
                        key: ValueKey('void_reason_${v.voidSource}'),
                        enabled: !busy,
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
  final source.LedgerRow row;
  final bool online, busy;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final bloc = context.read<EvidenceBloc>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        LedgerRow(
          amount: row.amount,
          label: entryTypeText(l, row.type),
          caption: l.businessDate(formatDate(row.date, l.localeName)),
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
          TextAction(
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
          TextAction(
            text: l.correctionOf(row.correctionOf!),
            onPressed: () => openSourceEvidence(context, [
              row.correctionOf!,
            ], l.savedEntryFormula),
          ),
        if (row.rawText.isEmpty)
          TextAction(
            text: l.originalRow,
            onPressed: !online || busy
                ? null
                : () => bloc.add(OpenSourceDetail(row.id)),
          )
        else
          SelectableCaption(
            row.rawText,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        if (row.status != 'voided')
          TextAction(
            text: l.undo,
            onPressed: !online || busy
                ? null
                : () => bloc.add(BeginSourceVoid(row.id)),
          ),
      ],
    );
  }
}
