import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/widgets/confirmation_sheet.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../bloc/draft_bloc.dart';

Future<void> openReminderSheet(
  BuildContext context,
  String customerId, [
  String tone = 'gentle',
]) async {
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    sheetAnimationStyle: const AnimationStyle(
      duration: Duration.zero,
      reverseDuration: Duration.zero,
    ),
    builder: (_) => BlocProvider(
      create: (_) => getIt<DraftBloc>()..add(OpenReminder(customerId, tone)),
      child: const ReminderDraftSheet(),
    ),
  );
}

class ReminderDraftSheet extends StatelessWidget {
  const ReminderDraftSheet({super.key});
  @override
  Widget build(BuildContext context) => BlocBuilder<DraftBloc, DraftState>(
    builder: (context, state) {
      final l = AppLocalizations.of(context), v = state.view;
      final bloc = context.read<DraftBloc>();
      final busy = state is DraftLoading;
      final shareReady =
          !busy && v.online && v.pending == null && v.draft?.canShare == true;
      return ConfirmationSheet(
        title: l.collectionDraftTitle,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (v.draft != null)
              Text(
                l.partyOption(v.draft!.name, v.draft!.id),
                style: Theme.of(context).textTheme.titleMedium,
              ),
            const SizedBox(height: AppDimens.md),
            Text(l.collectionTone),
            SegmentedControl(
              choices: {
                'gentle': l.collectionGentle,
                'normal': l.collectionNormal,
                'firm': l.collectionFirm,
              },
              selected: v.tone,
              onSelected: (tone) {
                if (!busy && v.pending == null) {
                  bloc.add(OpenReminder(v.customerId, tone));
                }
              },
            ),
            const SizedBox(height: AppDimens.lg),
            if (busy) const InlineProgress(),
            if (state is DraftFailure)
              FailureView(
                failure: state.failure,
                onRetry: () => bloc.add(
                  v.pending == null
                      ? OpenReminder(v.customerId, v.tone)
                      : const RetryReminderLog(),
                ),
              ),
            if (!v.online) InfoStrip(text: l.needsConnection, offline: true),
            if (v.pending != null) ...[
              InfoStrip(text: l.collectionLogFailed, error: true),
              TextAction(
                text: l.collectionRetryLog,
                onPressed: !busy && v.online
                    ? () => bloc.add(const RetryReminderLog())
                    : null,
              ),
            ],
            if (v.draft != null) ...[
              for (final figure in v.draft!.figures)
                LedgerRow(
                  amount: figure,
                  label: l.collectionOverdueAmount,
                  onTap: () => openEvidence(context, figure),
                ),
              const SizedBox(height: AppDimens.md),
              ReminderTextField(
                text: v.text,
                enabled: !busy && v.pending == null,
                onChanged: (text) => bloc.add(EditReminder(text)),
              ),
              const SizedBox(height: AppDimens.md),
              InfoStrip(text: l.collectionReview),
              if (v.draft!.status == 'drafted' &&
                  v.draft!.reviewStatus != 'APPROVED')
                InfoStrip(text: l.collectionTemplatePending),
              const SizedBox(height: AppDimens.lg),
              ActionGroup(
                children: [
                  PrimaryButton(
                    key: const ValueKey('collection_whatsapp'),
                    text: l.collectionOpenWhatsapp,
                    onPressed: shareReady
                        ? () => bloc.add(const ShareReminder('whatsapp'))
                        : null,
                  ),
                  SecondaryButton(
                    key: const ValueKey('collection_copy'),
                    text: l.collectionCopy,
                    onPressed: shareReady
                        ? () => bloc.add(const ShareReminder('copy'))
                        : null,
                  ),
                ],
              ),
              const SizedBox(height: AppDimens.md),
              Text(
                l.collectionShareNotice,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ] else if (!busy)
              InfoStrip(text: l.collectionNoDraft),
            if (v.receipt != null) ...[
              const SizedBox(height: AppDimens.lg),
              InfoStrip(
                key: const ValueKey('reminder_confirmed'),
                text: v.receipt!.channel == 'copy'
                    ? l.collectionCopiedLogged
                    : l.collectionHandoffLogged,
              ),
            ],
          ],
        ),
      );
    },
  );
}

class ReminderTextField extends StatefulWidget {
  const ReminderTextField({
    required this.text,
    required this.enabled,
    required this.onChanged,
    super.key,
  });
  final String text;
  final bool enabled;
  final ValueChanged<String> onChanged;
  @override
  State<ReminderTextField> createState() => _ReminderTextFieldState();
}

class _ReminderTextFieldState extends State<ReminderTextField> {
  late final controller = TextEditingController(text: widget.text);
  @override
  void didUpdateWidget(ReminderTextField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (controller.text != widget.text) {
      controller.value = TextEditingValue(
        text: widget.text,
        selection: TextSelection.collapsed(offset: widget.text.length),
      );
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextFormField(
    key: const ValueKey('collection_draft_text'),
    controller: controller,
    enabled: widget.enabled,
    minLines: 4,
    maxLines: 10,
    decoration: InputDecoration(
      labelText: AppLocalizations.of(context).collectionDraftField,
    ),
    onChanged: widget.onChanged,
  );
}
