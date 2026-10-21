import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/amount_label.dart';
import '../../../../core/widgets/chat_bubble.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/merchant_menu.dart';
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
      return Scaffold(
        appBar: AppBar(
          title: Text(l.chatTitle),
          actions: const [MerchantMenu()],
        ),
        bottomNavigationBar: const MerchantNavigation(),
        body: SafeArea(
          child: Align(
            alignment: AlignmentDirectional.topCenter,
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppDimens.contentMaxWidth,
              ),
              child: Column(
                children: [
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.all(AppDimens.lg),
                      children: [
                        if (v.turns.isEmpty) InfoStrip(text: l.chatWelcome),
                        for (final turn in v.turns) ...[
                          Align(
                            alignment: AlignmentDirectional.centerStart,
                            child: ChatBubble(
                              text: turn.question,
                              merchant: true,
                            ),
                          ),
                          const SizedBox(height: AppDimens.md),
                          ChatBubble(
                            text: turn.reply.text,
                            footer: ChatEvidence(turn: turn),
                          ),
                          const SizedBox(height: AppDimens.xl),
                        ],
                        if (state is ChatLoading)
                          InfoStrip(text: l.checkingLedger),
                        if (state is ChatFailure)
                          InfoStrip(text: failureText(l, state.failure)),
                      ],
                    ),
                  ),
                  if (!v.online)
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppDimens.lg,
                      ),
                      child: Column(
                        children: [
                          InfoStrip(text: l.chatNeedsConnection),
                          SecondaryButton(
                            text: l.retry,
                            onPressed: () => bloc.add(const RecheckChat()),
                          ),
                        ],
                      ),
                    ),
                  SizedBox(
                    height: 64,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppDimens.lg,
                      ),
                      children: [
                        PromptChip(
                          text: l.promptSupplier,
                          onPressed: () => bloc.add(FillChat(l.promptSupplier)),
                        ),
                        const SizedBox(width: AppDimens.sm),
                        PromptChip(
                          text: l.promptDebts,
                          onPressed: () => bloc.add(FillChat(l.promptDebts)),
                        ),
                        const SizedBox(width: AppDimens.sm),
                        PromptChip(
                          text: l.promptWeek,
                          onPressed: () => bloc.add(FillChat(l.promptWeek)),
                        ),
                      ],
                    ),
                  ),
                  const Padding(
                    padding: EdgeInsets.all(AppDimens.lg),
                    child: ChatComposer(),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    },
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
                onPressed: () =>
                    openSourceEvidence(context, metric.sources, metric.formula),
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
class ChatComposer extends StatefulWidget {
  const ChatComposer({super.key});
  @override
  State<ChatComposer> createState() => _ChatComposerState();
}

class _ChatComposerState extends State<ChatComposer> {
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
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            key: const ValueKey('chat_input'),
            controller: controller,
            minLines: 1,
            maxLines: 3,
            maxLength: 4000,
            enabled: state is! ChatLoading,
            decoration: InputDecoration(
              labelText: l.chatInput,
              counterText: '',
            ),
            onChanged: (text) => bloc.add(TypeChat(text)),
          ),
          const SizedBox(height: AppDimens.sm),
          PrimaryButton(
            key: const ValueKey('chat_send'),
            text: l.send,
            onPressed: !state.view.online || state is ChatLoading
                ? null
                : () => bloc.add(const SubmitChat()),
          ),
        ],
      );
    },
  );
}
