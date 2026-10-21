import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../bloc/entry_bloc.dart';

String entryTypeText(AppLocalizations l, String type) => switch (type) {
  'CASH_SALE' => l.cashSale,
  'CREDIT_SALE' => l.creditSale,
  'CREDIT_COLLECTION' => l.collection,
  'SUPPLIER_INVOICE' => l.supplierInvoice,
  'SUPPLIER_PAYMENT' => l.supplierPayment,
  'OPERATING_EXPENSE' => l.operatingExpense,
  'OWNER_DRAWING' => l.ownerDrawing,
  'CAPITAL_INJECTION' => l.capitalInjection,
  'DAILY_CASH_COUNT' => l.cashCount,
  _ => l.entryTitle,
};

class EntryPage extends StatelessWidget {
  const EntryPage({this.fields = const {}, super.key});
  final Map<String, String> fields;
  @override
  Widget build(BuildContext context) => MerchantPage(
    title: AppLocalizations.of(context).entryTitle,
    children: [EntryPanel(fields: fields)],
  );
}

class EntryPanel extends StatelessWidget {
  const EntryPanel({
    this.fields = const {},
    this.onSaved,
    this.lockedDate = false,
    super.key,
  });
  final Map<String, String> fields;
  final VoidCallback? onSaved;
  final bool lockedDate;
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<EntryBloc>()..add(OpenEntry(fields)),
    child: BlocListener<EntryBloc, EntryState>(
      listenWhen: (a, b) => a.view.saved != b.view.saved,
      listener: (_, state) {
        if (state.view.saved != null) onSaved?.call();
      },
      child: EntryForm(lockedDate: lockedDate),
    ),
  );
}

class EntryForm extends StatelessWidget {
  const EntryForm({this.lockedDate = false, super.key});
  final bool lockedDate;
  @override
  Widget build(BuildContext context) => BlocBuilder<EntryBloc, EntryState>(
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final v = state.view;
      final bloc = context.read<EntryBloc>();
      final busy = state is EntryLoading;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (busy) const LinearProgressIndicator(),
          if (!v.online) ...[
            InfoStrip(text: l.needsConnection),
            SecondaryButton(
              text: l.retry,
              onPressed: () => bloc.add(const RecheckEntry()),
            ),
          ],
          if (state is EntryFailure)
            InfoStrip(text: failureText(l, state.failure)),
          if (v.mode == EntryMode.edit) ...[
            DropdownButtonFormField<String>(
              key: const ValueKey('entry_type'),
              initialValue: v.draft.type,
              isExpanded: true,
              decoration: InputDecoration(labelText: l.entryType),
              items: [
                for (final type in entryTypes)
                  DropdownMenuItem(
                    value: type,
                    child: Text(entryTypeText(l, type)),
                  ),
              ],
              onChanged: busy
                  ? null
                  : (value) {
                      if (value != null) bloc.add(ChangeEntry('type', value));
                    },
            ),
            EntryField(
              field: 'business_date',
              label: l.businessDateInput,
              readOnly: lockedDate,
            ),
            EntryField(
              field: 'amount_iqd',
              label: l.amountInput,
              numeric: true,
            ),
            if (v.needsParty) ...[
              if (v.parties.isNotEmpty)
                DropdownButtonFormField<String>(
                  key: const ValueKey('party_choice'),
                  isExpanded: true,
                  initialValue:
                      v.parties.containsKey(v.draft.fields['counterparty_id'])
                      ? v.draft.fields['counterparty_id']
                      : null,
                  decoration: InputDecoration(labelText: l.partyInput),
                  items: [
                    for (final p in v.parties.entries)
                      DropdownMenuItem(
                        value: p.key,
                        child: Text(
                          l.partyOption(p.value, p.key),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: busy
                      ? null
                      : (value) {
                          if (value != null) {
                            bloc.add(ChangeEntry('counterparty_id', value));
                          }
                        },
                )
              else
                EntryField(field: 'counterparty_id', label: l.partyIdInput),
            ],
            if (v.needsObligation)
              EntryField(field: 'obligation_id', label: l.obligationInput),
            if (v.needsDue)
              EntryField(field: 'due_date', label: l.dueDateInput),
            const EntryField(field: 'note', label: null),
            if (v.draft.fields['correction_of_source_id']
                case final String original)
              InfoStrip(text: l.correctionOf(original)),
            const SizedBox(height: AppDimens.lg),
            PrimaryButton(
              key: const ValueKey('entry_review'),
              text: l.reviewEntry,
              onPressed: !v.online || busy
                  ? null
                  : () => bloc.add(const PrepareEntry()),
            ),
          ],
          if (v.mode == EntryMode.confirm) ...[
            LedgerCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    v.needsParty
                        ? l.entryConfirmation(
                            entryTypeText(l, v.draft.type),
                            formatDate(v.draft.date, l.localeName),
                            v.partyName,
                          )
                        : l.entryGeneralConfirmation(
                            entryTypeText(l, v.draft.type),
                            formatDate(v.draft.date, l.localeName),
                          ),
                  ),
                  if (v.amount != null)
                    AmountView(
                      amount: v.amount!,
                      label: l.amountInput,
                      exact: true,
                    ),
                  if (v.draft.fields['obligation_id']
                      case final String obligation)
                    Text(l.obligationReference(obligation)),
                ],
              ),
            ),
            PrimaryButton(
              key: const ValueKey('entry_save'),
              text: l.confirm,
              onPressed: !v.online || busy
                  ? null
                  : () => bloc.add(const ConfirmEntry()),
            ),
            SecondaryButton(
              text: l.edit,
              onPressed: busy ? null : () => bloc.add(const EditEntry()),
            ),
          ],
          if (v.mode == EntryMode.saved ||
              v.mode == EntryMode.undo ||
              v.mode == EntryMode.voided) ...[
            InfoStrip(text: l.savedSource(v.saved!.sourceId)),
            SecondaryButton(
              text: l.evidence,
              onPressed: () => openSourceEvidence(context, [
                v.saved!.sourceId,
              ], l.savedEntryFormula),
            ),
            if (v.mode == EntryMode.saved)
              SecondaryButton(
                text: l.undo,
                onPressed: !v.online || busy
                    ? null
                    : () => bloc.add(const BeginUndo()),
              ),
            if (v.mode == EntryMode.undo) ...[
              InfoStrip(text: l.undoNotice),
              TextFormField(
                key: const ValueKey('undo_reason'),
                initialValue: v.reason,
                decoration: InputDecoration(labelText: l.voidReason),
                onChanged: (value) => bloc.add(ChangeUndoReason(value)),
              ),
              PrimaryButton(
                text: l.confirmUndo,
                onPressed: !v.online || busy
                    ? null
                    : () => bloc.add(const ConfirmUndo()),
              ),
            ],
            if (v.mode == EntryMode.voided) ...[
              InfoStrip(text: l.voidSaved(v.voided!.voidId, v.voided!.reason)),
              SecondaryButton(
                text: l.correctEntry,
                onPressed: !v.online
                    ? null
                    : () => context.push(
                        Uri(
                          path: '/entry',
                          queryParameters: {
                            ...v.draft.fields,
                            'correction_of_source_id': v.saved!.sourceId,
                          },
                        ).toString(),
                      ),
              ),
            ],
            if (v.mode != EntryMode.undo)
              SecondaryButton(
                text: l.newEntry,
                onPressed: busy ? null : () => bloc.add(const OpenEntry()),
              ),
          ],
        ],
      );
    },
  );
}

class EntryField extends StatelessWidget {
  const EntryField({
    required this.field,
    required this.label,
    this.numeric = false,
    this.readOnly = false,
    super.key,
  });
  final String field;
  final String? label;
  final bool numeric;
  final bool readOnly;
  @override
  Widget build(BuildContext context) {
    final state = context.watch<EntryBloc>().state;
    return Padding(
      padding: const EdgeInsets.only(top: AppDimens.md),
      child: TextFormField(
        key: ValueKey(field),
        initialValue: state.view.draft.fields[field],
        keyboardType: numeric ? TextInputType.number : TextInputType.text,
        enabled: state is! EntryLoading,
        readOnly: readOnly,
        decoration: InputDecoration(
          labelText: label ?? AppLocalizations.of(context).noteInput,
        ),
        onChanged: (value) =>
            context.read<EntryBloc>().add(ChangeEntry(field, value)),
      ),
    );
  }
}
