import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../constants/app_dimens.dart';
import 'merchant_shell.dart';
export 'merchant_navigation.dart' show MerchantNavigation;

class MerchantPage extends StatelessWidget {
  const MerchantPage({
    required this.title,
    required this.children,
    this.actions = const [],
    this.columns = false,
    this.form = false,
    this.bottomBar,
    this.onRefresh,
    super.key,
  });
  final String title;
  final List<Widget> children, actions;
  final bool columns, form;
  final Widget? bottomBar;
  final Future<void> Function()? onRefresh;
  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final gutter = AppDimens.screenGutter(width);
    final path = GoRouterState.of(context).uri.path;
    final max = form || ['/entry', '/close'].contains(path)
        ? AppDimens.formMaxWidth
        : columns && width >= AppDimens.expandedBreakpoint
        ? AppDimens.columnsMaxWidth
        : width < AppDimens.expandedBreakpoint
        ? AppDimens.mediumContentMaxWidth
        : AppDimens.contentMaxWidth;
    Widget content = ListView(
      key: const ValueKey('merchant_scroll'),
      physics: const AlwaysScrollableScrollPhysics(),
      padding: EdgeInsets.all(gutter),
      children: [
        if (actions.isNotEmpty)
          Align(
            alignment: AlignmentDirectional.centerEnd,
            child: Wrap(children: actions),
          ),
        ...children,
      ],
    );
    if (onRefresh != null) {
      content = RefreshIndicator(onRefresh: onRefresh!, child: content);
    }
    return MerchantScaffold(
      title: title,
      bottomBar: bottomBar,
      body: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: max + gutter * 2),
          child: content,
        ),
      ),
    );
  }
}
