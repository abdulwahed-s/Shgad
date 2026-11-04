import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../constants/app_dimens.dart';
import 'merchant_navigation.dart';
import 'page_header.dart';

class MerchantScaffold extends StatelessWidget {
  const MerchantScaffold({
    required this.title,
    required this.body,
    this.bottomBar,
    this.actions = const [],
    this.taskFlow,
    super.key,
  });
  final String title;
  final Widget body;
  final Widget? bottomBar;
  final List<Widget> actions;
  final bool? taskFlow;
  @override
  Widget build(BuildContext context) {
    final window = MediaQuery.sizeOf(context).width;
    final path = GoRouterState.of(context).uri.path;
    final pushed =
        taskFlow ??
        [
          '/entry',
          '/close',
          '/import',
          '/sample',
          '/collections',
        ].contains(path);
    final compact = window < AppDimens.compactBreakpoint;
    final expanded = window >= AppDimens.expandedBreakpoint;
    final scaffold = LayoutBuilder(
      builder: (context, bounds) {
        final text =
            TextPainter(
              text: TextSpan(
                text: title,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              textDirection: Directionality.of(context),
              textScaler: MediaQuery.textScalerOf(context),
            )..layout(
              maxWidth:
                  (bounds.maxWidth -
                          AppDimens.lg * 2 -
                          (pushed || compact ? AppDimens.minTarget : 0))
                      .clamp(AppDimens.minTarget, double.infinity),
            );
        final minimum = MediaQuery.textScalerOf(
          context,
        ).scale(AppDimens.toolbarHeight);
        final header = text.height + AppDimens.lg > minimum
            ? text.height + AppDimens.lg
            : minimum;
        return Scaffold(
          appBar: PageHeader(
            title: title,
            height: header,
            onBack: pushed
                ? () {
                    if (context.canPop()) {
                      context.pop();
                    } else {
                      context.go('/');
                    }
                  }
                : null,
          ),
          body: SafeArea(child: body),
          bottomNavigationBar: bottomBar != null
              ? DecoratedBox(
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    border: Border(
                      top: BorderSide(
                        color: Theme.of(context).colorScheme.outline,
                      ),
                    ),
                  ),
                  child: SafeArea(
                    top: false,
                    child: Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: compact
                            ? AppDimens.lg
                            : expanded
                            ? AppDimens.xxl
                            : AppDimens.xl,
                        vertical: AppDimens.md,
                      ),
                      child: Center(
                        heightFactor: 1,
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(
                            maxWidth: AppDimens.formMaxWidth,
                          ),
                          child: bottomBar!,
                        ),
                      ),
                    ),
                  ),
                )
              : compact && !pushed
              ? const MerchantNavigation()
              : null,
        );
      },
    );
    return compact
        ? scaffold
        : Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              MerchantNavigation(rail: true, extended: expanded),
              Expanded(child: scaffold),
            ],
          );
  }
}

class ScreenColumns extends StatelessWidget {
  const ScreenColumns({required this.start, required this.end, super.key});
  final Widget start, end;
  @override
  Widget build(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= AppDimens.expandedBreakpoint
      ? Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(child: start),
            const SizedBox(width: AppDimens.xl),
            Expanded(child: end),
          ],
        )
      : Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            start,
            const SizedBox(height: AppDimens.xl),
            end,
          ],
        );
}
