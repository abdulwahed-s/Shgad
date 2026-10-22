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
    return LayoutBuilder(
      builder: (context, bounds) => Align(
        alignment: merchant
            ? AlignmentDirectional.centerStart
            : AlignmentDirectional.centerEnd,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: bounds.maxWidth * (merchant ? .80 : .88),
          ),
          child: Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppDimens.lg,
              vertical: AppDimens.md,
            ),
            decoration: BoxDecoration(
              color: merchant
                  ? theme.colorScheme.secondaryContainer
                  : theme.colorScheme.surface,
              border: merchant
                  ? null
                  : Border.all(color: theme.colorScheme.outline),
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
                if (footer != null) ...[
                  const SizedBox(height: AppDimens.md),
                  const Divider(),
                  const SizedBox(height: AppDimens.md),
                  footer!,
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
