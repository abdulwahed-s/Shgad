import '../../../../core/widgets/entry_type_text.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/confirmation_sheet.dart';
import '../../../../core/theme/app_theme.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../bloc/entry_bloc.dart';

class EntryPage extends StatelessWidget {
  const EntryPage({this.fields = const {}, super.key});
  final Map<String, String> fields;
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<EntryBloc>()..add(OpenEntry(fields)),
    child: const _EntryPageView(),
  );
}

class _EntryPageView extends StatelessWidget {
  const _EntryPageView();
  @override
  Widget build(BuildContext context) => BlocListener<EntryBloc, EntryState>(
    listenWhen: (a, b) =>
        a.view.mode != b.view.mode && b.view.mode == EntryMode.confirm,
    listener: (context, state) async {
      final bloc = context.read<EntryBloc>();
      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        sheetAnimationStyle: const AnimationStyle(
          duration: Duration.zero,
          reverseDuration: Duration.zero,
        ),
        builder: (_) => BlocProvider.value(
          value: bloc,
          child: BlocListener<EntryBloc, EntryState>(
            listenWhen: (a, b) => b.view.mode != EntryMode.confirm,
            listener: (context, state) => Navigator.of(context).pop(),
            child: ConfirmationSheet(
              title: AppLocalizations.of(context).reviewEntry,
              child: const EntryForm(),
            ),
          ),
        ),
      );
      if (!bloc.isClosed && bloc.state.view.mode == EntryMode.confirm) {
        bloc.add(const EditEntry());
      }
    },
    child: BlocBuilder<EntryBloc, EntryState>(
      builder: (context, state) {
        final l = AppLocalizations.of(context);
        final v = state.view;
        final bloc = context.read<EntryBloc>();
        return MerchantPage(
          title: l.entryTitle,
          form: true,
          bottomBar: v.mode == EntryMode.edit
              ? SizedBox(
                  width: AppDimens.formMaxWidth,
                  child: PrimaryButton(
                    key: const ValueKey('entry_review'),
                    text: l.reviewEntry,
                    onPressed: !v.online || state is EntryLoading
                        ? null
                        : () => bloc.add(const PrepareEntry()),
                  ),
                )
              : null,
          children: const [
            EntryForm(inlineConfirmation: false, showReview: false),
          ],
        );
      },
    ),
  );
}

class EntryPanel extends StatefulWidget {
  const EntryPanel({
    this.fields = const {},
    this.onSaved,
    this.onVoided,
    this.lockedDate = false,
    this.amountFirst = false,
    super.key,
  });
  final Map<String, String> fields;
  final VoidCallback? onSaved;
  final VoidCallback? onVoided;
  final bool lockedDate;
  final bool amountFirst;
  @override
  State<EntryPanel> createState() => _EntryPanelState();
}

class _EntryPanelState extends State<EntryPanel>
    with AutomaticKeepAliveClientMixin<EntryPanel> {
  // A daily-close refresh can move this result outside the lazy list's cache.
  // Keep its existing BLoC and saved/undo presentation until the route closes.
  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return BlocProvider(
      create: (_) => getIt<EntryBloc>()..add(OpenEntry(widget.fields)),
      child: BlocListener<EntryBloc, EntryState>(
        listenWhen: (a, b) =>
            a.view.saved != b.view.saved || a.view.voided != b.view.voided,
        listener: (_, state) {
          if (state.view.voided != null) {
            widget.onVoided?.call();
          } else if (state.view.saved != null) {
            widget.onSaved?.call();
          }
        },
        child: EntryForm(
          lockedDate: widget.lockedDate,
          amountFirst: widget.amountFirst,
        ),
      ),
    );
  }
}

class EntryForm extends StatelessWidget {
  const EntryForm({
    this.lockedDate = false,
    this.inlineConfirmation = true,
    this.showReview = true,
    this.amountFirst = false,
    super.key,
  });
  final bool lockedDate, inlineConfirmation, showReview, amountFirst;
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
            InfoStrip(text: failureText(l, state.failure), error: true),
          if (v.mode == EntryMode.edit ||
              v.mode == EntryMode.confirm && !inlineConfirmation) ...[
            if (amountFirst)
              EntryField(
                field: 'amount_iqd',
                label: v.draft.type == 'DAILY_CASH_COUNT'
                    ? l.cashCount
                    : l.amountInput,
                numeric: true,
              ),
            FieldLabel(
              label: l.entryType,
              group: true,
              child: ChoiceChips(
                key: const ValueKey('entry_type'),
                choices: {
                  for (final type in entryTypes) type: entryTypeText(l, type),
                },
                selected: v.draft.type,
                onSelected: busy
                    ? null
                    : (value) => bloc.add(ChangeEntry('type', value)),
              ),
            ),
            if (!amountFirst)
              EntryField(
                field: 'amount_iqd',
                label: l.amountInput,
                numeric: true,
              ),
            if (v.needsParty) ...[
              if (v.parties.isNotEmpty)
                ledgerDropdown<String>(
                  context,
                  decoration: InputDecoration(labelText: l.partyInput),
                  key: const ValueKey('party_choice'),
                  isExpanded: true,
                  initialValue:
                      v.parties.containsKey(v.draft.fields['counterparty_id'])
                      ? v.draft.fields['counterparty_id']
                      : null,
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
            EntryField(
              field: 'business_date',
              label: l.businessDateInput,
              readOnly: lockedDate,
            ),
            const EntryField(field: 'note', label: null),
            if (v.draft.fields['correction_of_source_id']
                case final String original)
              InfoStrip(text: l.correctionOf(original)),
            const SizedBox(height: AppDimens.lg),
            if (showReview)
              PrimaryButton(
                key: const ValueKey('entry_review'),
                text: l.reviewEntry,
                onPressed: !v.online || busy
                    ? null
                    : () => bloc.add(const PrepareEntry()),
              ),
          ],
          if (v.mode == EntryMode.confirm && inlineConfirmation) ...[
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
            const SizedBox(height: AppDimens.md),
            ActionGroup(
              children: [
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
            ),
          ],
          if (v.mode == EntryMode.saved ||
              v.mode == EntryMode.undo ||
              v.mode == EntryMode.voided) ...[
            InfoStrip(text: l.savedSource(v.saved!.sourceId)),
            const SizedBox(height: AppDimens.md),
            ActionGroup(
              children: [
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
              ],
            ),
            if (v.mode == EntryMode.undo) ...[
              const SizedBox(height: AppDimens.md),
              InfoStrip(text: l.undoNotice),
              const SizedBox(height: AppDimens.md),
              ledgerTextField(
                context,
                key: const ValueKey('undo_reason'),
                enabled: !busy,
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
              const SizedBox(height: AppDimens.md),
              InfoStrip(text: l.voidSaved(v.voided!.voidId, v.voided!.reason)),
              const SizedBox(height: AppDimens.md),
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
            if (v.mode != EntryMode.undo) ...[
              const SizedBox(height: AppDimens.md),
              SecondaryButton(
                text: l.newEntry,
                onPressed: busy ? null : () => bloc.add(const OpenEntry()),
              ),
            ],
          ],
        ],
      );
    },
  );
}

class EntryField extends StatefulWidget {
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
  State<EntryField> createState() => _EntryFieldState();
}

/// Keeps the editing controller in step with server-loaded BLoC values.
class _EntryFieldState extends State<EntryField> {
  late final TextEditingController controller;
  @override
  void initState() {
    super.initState();
    controller = TextEditingController(
      text: context.read<EntryBloc>().state.view.draft.fields[widget.field],
    );
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BlocConsumer<EntryBloc, EntryState>(
    listenWhen: (a, b) =>
        a.view.draft.fields[widget.field] != b.view.draft.fields[widget.field],
    listener: (_, state) {
      final text = state.view.draft.fields[widget.field] ?? '';
      if (controller.text != text) {
        controller.value = TextEditingValue(
          text: text,
          selection: TextSelection.collapsed(offset: text.length),
        );
      }
    },
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final bloc = context.read<EntryBloc>();
      final enabled = state is! EntryLoading;
      final label = widget.label ?? l.noteInput;
      if (widget.numeric) {
        return AmountField(
          fieldKey: ValueKey(widget.field),
          controller: controller,
          label: label,
          enabled: enabled,
          onChanged: (value) => bloc.add(ChangeEntry(widget.field, value)),
        );
      }
      if (widget.field == 'business_date' || widget.field == 'due_date') {
        return DateField(
          fieldKey: ValueKey(widget.field),
          label: label,
          value: state.view.draft.fields[widget.field] ?? '',
          businessDate: state.view.draft.date,
          enabled: enabled,
          locked: widget.readOnly,
          onChanged: (value) => bloc.add(ChangeEntry(widget.field, value)),
        );
      }
      return FieldLabel(
        label: label,
        child: TextFormField(
          key: ValueKey(widget.field),
          controller: controller,
          enabled: enabled,
          readOnly: widget.readOnly,
          style: Theme.of(
            context,
          ).extension<LedgerStyles>()!.input(enabled: enabled),
          onChanged: (value) => bloc.add(ChangeEntry(widget.field, value)),
        ),
      );
    },
  );
}
