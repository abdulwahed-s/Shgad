import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../theme/app_motion.dart';

class ConfirmationSheet extends StatelessWidget {
  const ConfirmationSheet({
    required this.title,
    required this.child,
    super.key,
  });
  final String title;
  final Widget child;
  @override
  Widget build(BuildContext context) => SoftEntrance(
    child: SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.only(
          left: AppDimens.lg,
          right: AppDimens.lg,
          top: AppDimens.sm,
          bottom: AppDimens.lg + MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  tooltip: AppLocalizations.of(context).dismiss,
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close_outlined),
                ),
              ],
            ),
            const SizedBox(height: AppDimens.lg),
            child,
          ],
        ),
      ),
    ),
  );
}
