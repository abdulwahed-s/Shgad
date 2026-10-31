import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/step_indicator.dart';
import '../../../../core/widgets/section_label.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../../../core/widgets/entry_type_text.dart';
import '../../domain/entities/csv_import.dart';
import '../bloc/csv_bloc.dart';

String csvFieldText(AppLocalizations l, String field) => switch (field) {
  'source_id' => l.sourceIdField,
  'occurred_at' => l.eventTimeField,
  'business_date' => l.businessDateInput,
  'type' => l.entryType,
  'amount_iqd' => l.amountInput,
  'counterparty_id' => l.partyIdInput,
  'obligation_id' => l.obligationInput,
  'due_date' => l.dueDateInput,
  'category_id' => l.categoryField,
  'quantity' => l.quantityField,
  'description' => l.noteInput,
  'currency' => l.currencyField,
  'recorded_at' => l.recordedTimeField,
  _ => l.ignoreColumn,
};
String csvIssueText(AppLocalizations l, String code) => switch (code) {
  'MAPPING_UNRESOLVED' => l.errorMapping,
  'INVALID_AMOUNT' || 'INVALID_IQD' => l.errorAmount,
  'INVALID_DATE' || 'INVALID_TIMESTAMP' => l.errorDate,
  'UNKNOWN_COUNTERPARTY' => l.csvUnknownParty,
  'AMBIGUOUS_COUNTERPARTY' => l.csvAmbiguousParty,
  'UNKNOWN_TYPE' => l.csvUnknownType,
  'MISSING_DUE_DATE' => l.errorDueDate,
  'UNKNOWN_CATEGORY' => l.errorCategory,
  'IDEMPOTENCY_CONFLICT' => l.errorIdentity,
  'EXACT_DUPLICATE' => l.csvDuplicate,
  'CURRENCY_NOT_IQD' || 'INVALID_CURRENCY' => l.errorCurrency,
  _ => l.errorValidation,
};

String csvIssueDetails(AppLocalizations l, CsvIssue issue) => [
  if (issue.field != null) csvFieldText(l, issue.field!),
  csvIssueText(l, issue.code),
  for (final candidate in issue.candidates)
    '${candidate.displayName} (${candidate.id})',
].join(' · ');

class CsvPage extends StatelessWidget {
  const CsvPage({super.key});
  @override
  Widget build(BuildContext context) =>
      BlocProvider(create: (_) => getIt<CsvBloc>(), child: const _CsvView());
}

class _CsvView extends StatelessWidget {
  const _CsvView();
  @override
  Widget build(BuildContext context) => BlocBuilder<CsvBloc, CsvState>(
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final v = state.view;
      final bloc = context.read<CsvBloc>();
      final busy = state is CsvLoading;
      return MerchantPage(
        title: l.importTitle,
        children: [
          StepIndicator(
            labels: [l.chooseCsv, l.columnMapping, l.confirmImport],
            current: v.confirming || v.receipt != null
                ? 2
                : v.selection != null
                ? 1
                : 0,
          ),
          const SizedBox(height: AppDimens.lg),
          InfoStrip(text: l.syntheticCsvOnly),
          const SizedBox(height: AppDimens.lg),
          if (busy) const InlineProgress(),
          if (!v.online) ...[
            InfoStrip(text: l.needsConnection),
            const SizedBox(height: AppDimens.md),
            SecondaryButton(
              text: l.retry,
              onPressed: () => bloc.add(const RecheckCsv()),
            ),
          ],
          if (state is CsvFailure) ...[
            InfoStrip(text: failureText(l, state.failure), error: true),
            const SizedBox(height: AppDimens.md),
          ],
          if (v.receipt case final CsvReceipt receipt) ...[
            Text(
              l.savedBatch(receipt.id),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppDimens.sm),
            LedgerGroup(
              children: [
                Text(
                  l.importAccepted(
                    IqdFormatter.digits(
                      receipt.accepted.toString(),
                      l.localeName,
                    ),
                  ),
                ),
                Text(
                  l.importFlagged(
                    IqdFormatter.digits(
                      receipt.flagged.toString(),
                      l.localeName,
                    ),
                  ),
                ),
                Text(
                  l.importRejected(
                    IqdFormatter.digits(
                      receipt.rejected.toString(),
                      l.localeName,
                    ),
                  ),
                ),
                Text(
                  l.importDuplicates(
                    IqdFormatter.digits(
                      receipt.duplicates.toString(),
                      l.localeName,
                    ),
                  ),
                ),
              ],
            ),
            for (final issue in receipt.issues)
              Text(
                l.csvRowError(
                  IqdFormatter.digits(issue.row.toString(), l.localeName),
                  csvIssueDetails(l, issue),
                ),
              ),
            const SizedBox(height: AppDimens.md),
            ActionGroup(
              children: [
                PrimaryButton(
                  text: l.openToday,
                  onPressed: () => context.go('/'),
                ),
                SecondaryButton(
                  text: l.importAnother,
                  onPressed: () => bloc.add(const NewCsvImport()),
                ),
              ],
            ),
          ] else if (v.confirming) ...[
            LedgerCard(
              child: Text(
                l.importConfirmation(v.selection!.file.name, v.preview!.id),
              ),
            ),
            const SizedBox(height: AppDimens.md),
            ActionGroup(
              children: [
                PrimaryButton(
                  key: const ValueKey('csv_confirm'),
                  text: l.confirmImport,
                  onPressed: !v.online || busy
                      ? null
                      : () => bloc.add(const ConfirmCsvImport()),
                ),
                SecondaryButton(
                  text: l.edit,
                  onPressed: busy
                      ? null
                      : () => bloc.add(const EditCsvMapping()),
                ),
              ],
            ),
          ] else ...[
            if (v.selection != null)
              SecondaryButton(
                key: const ValueKey('csv_pick'),
                text: l.chooseCsv,
                onPressed: !v.online || busy
                    ? null
                    : () => bloc.add(const ChooseCsv()),
              )
            else
              PrimaryButton(
                key: const ValueKey('csv_pick'),
                text: l.chooseCsv,
                onPressed: !v.online || busy
                    ? null
                    : () => bloc.add(const ChooseCsv()),
              ),
            if (v.selection != null) ...[
              const SizedBox(height: AppDimens.md),
              Text(
                v.selection!.file.name,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(l.acknowledgeSynthetic),
                value: v.synthetic,
                onChanged: busy
                    ? null
                    : (value) => bloc.add(AcknowledgeSynthetic(value ?? false)),
              ),
              SectionLabel(text: l.columnMapping),
              for (final column in v.columns) ...[
                const SizedBox(height: AppDimens.md),
                SelectableCaption(
                  column.header,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                ledgerDropdown<String>(
                  context,
                  key: ValueKey('mapping_${column.header}_${column.target}'),
                  initialValue: column.target ?? '',
                  isExpanded: true,
                  decoration: InputDecoration(labelText: l.targetField),
                  items: [
                    DropdownMenuItem(value: '', child: Text(l.ignoreColumn)),
                    for (final field in csvTargets)
                      DropdownMenuItem(
                        value: field,
                        child: Text(
                          csvFieldText(l, field),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: busy
                      ? null
                      : (value) => bloc.add(
                          ChangeCsvColumn(
                            column.header,
                            value == '' ? null : value,
                          ),
                        ),
                ),
              ],
              const SizedBox(height: AppDimens.lg),
              ActionGroup(
                children: [
                  SecondaryButton(
                    text: l.suggestMapping,
                    onPressed: !v.online || busy || !v.synthetic
                        ? null
                        : () => bloc.add(const PreviewCsvFile(suggest: true)),
                  ),
                  SecondaryButton(
                    key: const ValueKey('csv_preview'),
                    text: l.previewMapping,
                    onPressed: !v.online || busy || !v.synthetic
                        ? null
                        : () => bloc.add(const PreviewCsvFile()),
                  ),
                ],
              ),
              const SizedBox(height: AppDimens.md),
              if (v.dirty && v.preview != null)
                InfoStrip(text: l.mappingChanged),
              if (v.preview != null) ...[
                SectionLabel(text: l.previewFiveRows),
                for (final field in v.preview!.missing)
                  Text(l.missingColumn(csvFieldText(l, field))),
                if (MediaQuery.sizeOf(context).width <
                    AppDimens.compactBreakpoint)
                  for (final row in v.preview!.rows)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppDimens.lg),
                      child: LedgerCard(child: CsvPreviewRowView(row: row)),
                    )
                else
                  CsvPreviewTable(rows: v.preview!.rows),
              ],
              const SizedBox(height: AppDimens.lg),
              PrimaryButton(
                key: const ValueKey('csv_prepare'),
                text: l.reviewImport,
                onPressed: !v.online || busy || !v.canConfirm
                    ? null
                    : () => bloc.add(const PrepareCsvImport()),
              ),
            ],
          ],
        ],
      );
    },
  );
}

class CsvPreviewRowView extends StatelessWidget {
  const CsvPreviewRowView({required this.row, super.key});
  final CsvPreviewRow row;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Divider(),
        Text(l.csvRow(IqdFormatter.digits(row.row.toString(), l.localeName))),
        if (row.sourceId != null)
          Text(row.sourceId!, style: Theme.of(context).textTheme.bodySmall),
        if (row.date != null)
          Text(l.businessDate(formatDate(row.date!, l.localeName))),
        if (row.amount != null)
          AmountView(
            amount: row.amount!,
            label: entryTypeText(l, row.type!),
            exact: true,
          ),
        for (final issue in row.issues)
          InfoStrip(text: csvIssueDetails(l, issue), error: true),
      ],
    );
  }
}

class CsvPreviewTable extends StatelessWidget {
  const CsvPreviewTable({required this.rows, super.key});
  final List<CsvPreviewRow> rows;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: DataTable(
            dataRowMinHeight: AppDimens.minTarget,
            dataRowMaxHeight: AppDimens.fieldHeight * 2,
            columns: [
              DataColumn(label: Text(l.businessDateInput)),
              DataColumn(label: Text(l.entryType)),
              DataColumn(label: Text(l.amountInput), numeric: true),
              DataColumn(label: Text(l.sourceIdField)),
            ],
            rows: [
              for (final row in rows)
                DataRow(
                  cells: [
                    DataCell(
                      Text(
                        row.date == null
                            ? l.errorDate
                            : formatDate(row.date!, l.localeName),
                      ),
                    ),
                    DataCell(
                      Text(
                        row.type == null
                            ? l.missing
                            : entryTypeText(l, row.type!),
                      ),
                    ),
                    DataCell(
                      row.amount == null
                          ? Text(l.missing)
                          : AmountView(
                              amount: row.amount!,
                              label: l.amountInput,
                              exact: true,
                              table: true,
                            ),
                    ),
                    DataCell(
                      SelectableCaption(
                        row.sourceId ?? l.missing,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ),
                  ],
                ),
            ],
          ),
        ),
        for (final row in rows)
          for (final issue in row.issues)
            Padding(
              padding: const EdgeInsets.only(top: AppDimens.sm),
              child: InfoStrip(
                text: l.csvRowError(
                  IqdFormatter.digits(row.row.toString(), l.localeName),
                  csvIssueDetails(l, issue),
                ),
                error: true,
              ),
            ),
      ],
    );
  }
}
