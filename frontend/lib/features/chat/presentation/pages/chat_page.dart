import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/domain/evidence_request.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/amount_label.dart';
import '../../../../core/widgets/balanced_text.dart';
import '../../../../core/widgets/chat_bubble.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_shell.dart';
import '../../../../core/widgets/chat_composer.dart' as shared;
import '../../../../core/theme/app_motion.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/chat_reply.dart';
import '../bloc/chat_bloc.dart';

class ChatPage extends StatelessWidget {
  const ChatPage({super.key});
  @override
  Widget build(BuildContext context) =>
      BlocProvider.value(value: getIt<ChatBloc>(), child: const _ChatView());
}

class _ChatView extends StatelessWidget {
  const _ChatView();
  @override
  Widget build(BuildContext context) => BlocBuilder<ChatBloc, ChatState>(
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final bloc = context.read<ChatBloc>();
      final v = state.view;
      final prompts = [l.promptSupplier, l.promptDebts, l.promptWeek];
      return MerchantScaffold(
        title: l.chatTitle,
        body: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppDimens.contentMaxWidth,
            ),
            child: Column(
              children: [
                Expanded(
                  child: ChatTranscript(
                    revision: v.turns.length,
                    children: [
                      if (v.turns.isEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: AppDimens.xxxl),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text(
                                l.chatInput,
                                style: Theme.of(context).textTheme.titleMedium,
                              ),
                              const SizedBox(height: AppDimens.sm),
                              Text(l.chatWelcome),
                              const SizedBox(height: AppDimens.xl),
                              LedgerCard(
                                child: Column(
                                  children: [
                                    for (
                                      var i = 0;
                                      i < prompts.length;
                                      i++
                                    ) ...[
                                      if (i > 0) const Divider(),
                                      ListTile(
                                        title: BalancedText(prompts[i]),
                                        onTap: () =>
                                            bloc.add(FillChat(prompts[i])),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      for (final turn in v.turns)
                        SoftEntrance(
                          key: ObjectKey(turn),
                          child: Column(
                            children: [
                              ChatBubble(text: turn.question, merchant: true),
                              const SizedBox(height: AppDimens.md),
                              ChatBubble(
                                text: turn.reply.text,
                                textDirection: TextDirection.rtl,
                                footer: ChatEvidence(turn: turn),
                              ),
                              const SizedBox(height: AppDimens.xl),
                            ],
                          ),
                        ),
                      if (state is ChatLoading)
                        Row(
                          children: [
                            const SizedBox(
                              width: AppDimens.inlineSpinner,
                              height: AppDimens.inlineSpinner,
                              child: CircularProgressIndicator(
                                strokeWidth: AppDimens.progressHeight,
                              ),
                            ),
                            const SizedBox(width: AppDimens.sm),
                            Expanded(child: Text(l.checkingLedger)),
                          ],
                        ),
                      if (state is ChatFailure) ...[
                        InfoStrip(
                          text: failureText(l, state.failure),
                          error: true,
                        ),
                        TextAction(
                          text: l.retry,
                          onPressed: () => bloc.add(const SubmitChat()),
                        ),
                      ],
                      if (!v.online) ...[
                        InfoStrip(text: l.chatNeedsConnection, offline: true),
                        TextAction(
                          text: l.retry,
                          onPressed: () => bloc.add(const RecheckChat()),
                        ),
                      ],
                    ],
                  ),
                ),
                const ChatDraftComposer(),
              ],
            ),
          ),
        ),
      );
    },
  );
}

class ChatTranscript extends StatefulWidget {
  const ChatTranscript({
    required this.children,
    required this.revision,
    super.key,
  });
  final List<Widget> children;
  final int revision;
  @override
  State<ChatTranscript> createState() => _ChatTranscriptState();
}

class _ChatTranscriptState extends State<ChatTranscript> {
  final controller = ScrollController();
  @override
  void didUpdateWidget(ChatTranscript old) {
    super.didUpdateWidget(old);
    if (old.revision != widget.revision) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && controller.hasClients) {
          final duration = AppMotion.sheet(context);
          if (duration == Duration.zero) {
            controller.jumpTo(controller.position.maxScrollExtent);
            return;
          }
          controller.animateTo(
            controller.position.maxScrollExtent,
            duration: duration,
            curve: Curves.easeOutCubic,
          );
        }
      });
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ListView(
    controller: controller,
    padding: EdgeInsets.all(
      AppDimens.screenGutter(MediaQuery.sizeOf(context).width),
    ),
    children: widget.children,
  );
}

class ChatEvidence extends StatelessWidget {
  const ChatEvidence({required this.turn, super.key});
  final ChatTurn turn;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final reply = turn.reply;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (reply.resolved != null)
          ResolvedChatContext(contextValue: reply.resolved!),
        if (reply.resolved == null)
          for (final contextValue in reply.contexts)
            ResolvedChatContext(contextValue: contextValue),
        for (final figure in reply.figures)
          AmountView(
            amount: figure,
            label: amountLabel(l, figure.label),
            onTap: () => openEvidence(context, figure),
          ),
        for (final metric in reply.metrics)
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(amountLabel(l, metric.label)),
              StatusLabel(kind: metric.kind),
              TextButton(
                onPressed: () => context.push(
                  '/evidence',
                  extra: EvidenceRequest(
                    metric.sources,
                    metric.formula,
                    queryEvidence: metric.queryEvidence,
                  ),
                ),
                child: Text(
                  metric.value == null
                      ? l.missing
                      : l.metricValue(
                          IqdFormatter.digits(
                            metric.value.toString(),
                            l.localeName,
                          ),
                          switch (metric.unit) {
                            'percent' => l.percentUnit,
                            'days' => l.daysUnit,
                            _ => l.countUnit,
                          },
                        ),
                ),
              ),
            ],
          ),
        if (reply.template) InfoStrip(text: l.templateReply),
        if (reply.collectionAction != null)
          SecondaryButton(
            text: reply.collectionAction!.kind == 'draft'
                ? l.collectionDraftTitle
                : l.collectionsTitle,
            onPressed: () => context.push(reply.collectionAction!.location),
          ),
        for (final option in reply.options)
          SecondaryButton(
            text: option.label,
            onPressed: () => context.read<ChatBloc>().add(
              ChooseChatOption(turn.question, option),
            ),
          ),
      ],
    );
  }
}

class ResolvedChatContext extends StatelessWidget {
  const ResolvedChatContext({required this.contextValue, super.key});
  final ChatContext contextValue;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          l.resolvedPeriod(
            formatDate(contextValue.start, l.localeName),
            formatDate(contextValue.end, l.localeName),
          ),
          style: Theme.of(context).textTheme.bodySmall,
        ),
        if (contextValue.partyId != null)
          Text(
            l.resolvedCustomer(
              contextValue.partyName ?? contextValue.partyId!,
              contextValue.partyId!,
            ),
            style: Theme.of(context).textTheme.bodySmall,
          ),
      ],
    );
  }
}

/// Controller lifecycle only; draft, readiness and all actions belong to ChatBloc.
class ChatDraftComposer extends StatefulWidget {
  const ChatDraftComposer({super.key});
  @override
  State<ChatDraftComposer> createState() => _ChatComposerState();
}

class _ChatComposerState extends State<ChatDraftComposer> {
  late final TextEditingController controller;
  @override
  void initState() {
    super.initState();
    controller = TextEditingController(
      text: context.read<ChatBloc>().state.view.draft,
    );
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => BlocConsumer<ChatBloc, ChatState>(
    listenWhen: (a, b) => a.view.revision != b.view.revision,
    listener: (_, state) {
      controller.value = TextEditingValue(
        text: state.view.draft,
        selection: TextSelection.collapsed(offset: state.view.draft.length),
      );
    },
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final bloc = context.read<ChatBloc>();
      final height =
          MediaQuery.sizeOf(context).height -
          MediaQuery.viewInsetsOf(context).bottom;
      return shared.ChatComposer(
        controller: controller,
        onChanged: (text) => bloc.add(TypeChat(text)),
        enabled: state is! ChatLoading,
        onSubmit: !state.view.online || state is ChatLoading
            ? null
            : () => bloc.add(const SubmitChat()),
        prompts: state.view.turns.isNotEmpty && height > AppDimens.formMaxWidth
            ? [
                for (final prompt in [
                  l.promptSupplier,
                  l.promptDebts,
                  l.promptWeek,
                ])
                  Padding(
                    padding: const EdgeInsetsDirectional.only(
                      end: AppDimens.sm,
                    ),
                    child: PromptChip(
                      text: prompt,
                      onPressed: () => bloc.add(FillChat(prompt)),
                    ),
                  ),
              ]
            : const [],
      );
    },
  );
}
