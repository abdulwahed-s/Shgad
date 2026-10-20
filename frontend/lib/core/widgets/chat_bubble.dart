import 'package:flutter/material.dart';

import '../constants/app_dimens.dart';

class ChatBubble extends StatelessWidget {
  const ChatBubble({required this.text, this.merchant = false, super.key});

  final String text;
  final bool merchant;

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
      child: Text(text, style: theme.textTheme.bodyLarge),
    );
  }
}
