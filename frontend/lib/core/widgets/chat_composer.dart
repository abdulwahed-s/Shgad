import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import 'ledger_widgets.dart';
import '../theme/app_theme.dart';
import 'focus_outline.dart';

class ChatComposer extends StatelessWidget {
  const ChatComposer({
    required this.controller,
    required this.onChanged,
    required this.onSubmit,
    this.enabled = true,
    this.prompts = const [],
    super.key,
  });
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  final VoidCallback? onSubmit;
  final bool enabled;
  final List<Widget> prompts;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final short =
        MediaQuery.sizeOf(context).height -
            MediaQuery.viewInsetsOf(context).bottom <
        AppDimens.chartHeight * 2;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outline),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: AppDimens.lg,
            vertical: short ? AppDimens.sm : AppDimens.lg,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (prompts.isNotEmpty) ...[
                SizedBox(
                  height: MediaQuery.textScalerOf(
                    context,
                  ).scale(AppDimens.fieldHeight),
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    children: prompts,
                  ),
                ),
                const SizedBox(height: AppDimens.sm),
              ],
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: CallbackShortcuts(
                      bindings: onSubmit == null
                          ? const {}
                          : {
                              const SingleActivator(LogicalKeyboardKey.enter):
                                  onSubmit!,
                            },
                      child: FocusOutline(
                        child: TextField(
                          key: const ValueKey('chat_input'),
                          controller: controller,
                          minLines: 1,
                          maxLines: short ? 1 : 4,
                          maxLength: 4000,
                          enabled: enabled,
                          style: Theme.of(
                            context,
                          ).extension<LedgerStyles>()!.input(enabled: enabled),
                          textInputAction: TextInputAction.send,
                          onSubmitted: onSubmit == null
                              ? null
                              : (_) => onSubmit!(),
                          onChanged: onChanged,
                          decoration: InputDecoration(
                            hintText: l.chatInput,
                            counterText: '',
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppDimens.sm),
                  ConstrainedBox(
                    constraints: const BoxConstraints(
                      minWidth: AppDimens.composerButtonWidth,
                    ),
                    child: PrimaryButton(
                      key: const ValueKey('chat_send'),
                      text: l.send,
                      onPressed: onSubmit,
                      compact: true,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
