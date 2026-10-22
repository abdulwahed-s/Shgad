import 'package:flutter/material.dart';

import '../constants/app_dimens.dart';

class ChatBubble extends StatelessWidget {
  const ChatBubble({
    required this.text,
    this.merchant = false,
    this.footer,
    this.textDirection,
    super.key,
  });

  final String text;
  final bool merchant;
  final Widget? footer;
  final TextDirection? textDirection;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppDimens.lg),
      decoration: BoxDecoration(
        color: merchant
            ? theme.colorScheme.secondaryContainer
            : theme.colorScheme.surface,
        border: Border.all(
          color: theme.colorScheme.outline,
          width: AppDimens.borderWidth,
        ),
        borderRadius: BorderRadius.circular(AppDimens.radiusMd),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            text,
            style: theme.textTheme.bodyLarge,
            textDirection: textDirection,
          ),
          ?footer,
        ],
      ),
    );
  }
}
