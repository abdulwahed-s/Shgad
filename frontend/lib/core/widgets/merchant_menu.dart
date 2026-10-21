import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';

class MerchantMenu extends StatelessWidget {
  const MerchantMenu({super.key});
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return PopupMenuButton<String>(
      tooltip: l.more,
      onSelected: (route) => context.push(route),
      itemBuilder: (_) => [
        PopupMenuItem(value: '/weekly', child: Text(l.weeklyTitle)),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppDimens.lg, vertical: AppDimens.md),
        child: Text(l.more),
      ),
    );
  }
}
