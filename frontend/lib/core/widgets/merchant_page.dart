import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import 'merchant_menu.dart';

class MerchantPage extends StatelessWidget {
  const MerchantPage({
    required this.title,
    required this.children,
    this.actions = const [],
    super.key,
  });
  final String title;
  final List<Widget> children, actions;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: const [MerchantMenu()]),
      body: SafeArea(
        child: Align(
          alignment: AlignmentDirectional.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppDimens.contentMaxWidth,
            ),
            child: ListView(
              padding: const EdgeInsets.all(AppDimens.lg),
              children: [
                if (actions.isNotEmpty)
                  Align(
                    alignment: AlignmentDirectional.centerEnd,
                    child: Wrap(children: actions),
                  ),
                ...children,
              ],
            ),
          ),
        ),
      ),
      bottomNavigationBar: const MerchantNavigation(),
    );
  }
}

class MerchantNavigation extends StatelessWidget {
  const MerchantNavigation({super.key});
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(AppDimens.sm),
        child: Row(
          children: [
            Expanded(
              child: TextButton(
                onPressed: () => context.go('/'),
                child: Text(l.todayTitle),
              ),
            ),
            Expanded(
              child: TextButton(
                onPressed: () => context.go('/debts'),
                child: Text(l.debtsTitle),
              ),
            ),
            Expanded(
              child: TextButton(
                onPressed: () => context.go('/debts'),
                child: Text(l.debtsTitle),
              ),
            ),
            Expanded(
              child: TextButton(
                onPressed: () => context.go('/chat'),
                child: Text(l.chatTitle),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
