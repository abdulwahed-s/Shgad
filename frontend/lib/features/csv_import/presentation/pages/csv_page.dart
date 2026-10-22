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
  'UNKNOWN_COUNTERPARTY' => l.errorParty,
  'UNKNOWN_CATEGORY' => l.errorCategory,
  'IDEMPOTENCY_CONFLICT' => l.errorIdentity,
  'EXACT_DUPLICATE' => l.csvDuplicate,
  'CURRENCY_NOT_IQD' || 'INVALID_CURRENCY' => l.errorCurrency,
  _ => l.errorValidation,
};

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
          InfoStrip(text: l.syntheticCsvOnly),
          if (busy) const LinearProgressIndicator(),
          if (!v.online) ...[
            InfoStrip(text: l.needsConnection),
            SecondaryButton(
              text: l.retry,
              onPressed: () => bloc.add(const RecheckCsv()),
            ),
          ],
          if (state is CsvFailure)
            InfoStrip(text: failureText(l, state.failure)),
          if (v.receipt case final CsvReceipt receipt) ...[
            Text(
              l.savedBatch(receipt.id),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              l.importAccepted(
                IqdFormatter.digits(receipt.accepted.toString(), l.localeName),
              ),
            ),
            Text(
              l.importFlagged(
                IqdFormatter.digits(receipt.flagged.toString(), l.localeName),
              ),
            ),
            Text(
              l.importRejected(
                IqdFormatter.digits(receipt.rejected.toString(), l.localeName),
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
            for (final issue in receipt.issues)
              Text(
                l.csvRowError(
                  IqdFormatter.digits(issue.row.toString(), l.localeName),
                  csvIssueText(l, issue.code),
                ),
              ),
            PrimaryButton(text: l.openToday, onPressed: () => context.go('/')),
            SecondaryButton(
              text: l.importAnother,
              onPressed: () => bloc.add(const NewCsvImport()),
            ),
          ] else if (v.confirming) ...[
            LedgerCard(
              child: Text(
                l.importConfirmation(v.selection!.file.name, v.preview!.id),
              ),
            ),
            PrimaryButton(
              key: const ValueKey('csv_confirm'),
              text: l.confirmImport,
              onPressed: !v.online || busy
                  ? null
                  : () => bloc.add(const ConfirmCsvImport()),
            ),
            SecondaryButton(
              text: l.edit,
              onPressed: busy ? null : () => bloc.add(const EditCsvMapping()),
            ),
          ] else ...[
            SecondaryButton(
              key: const ValueKey('csv_pick'),
              text: l.chooseCsv,
              onPressed: !v.online || busy
                  ? null
                  : () => bloc.add(const ChooseCsv()),
            ),
            if (v.selection != null) ...[
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
                Text(column.header),
                DropdownButtonFormField<String>(
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
              if (v.dirty && v.preview != null)
                InfoStrip(text: l.mappingChanged),
              if (v.preview != null) ...[
                SectionLabel(text: l.previewFiveRows),
                for (final field in v.preview!.missing)
                  Text(l.missingColumn(csvFieldText(l, field))),
                for (final row in v.preview!.rows) CsvPreviewRowView(row: row),
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
          InfoStrip(text: csvIssueText(l, issue.code)),
      ],
    );
  }
}
