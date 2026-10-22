import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../theme/app_motion.dart';
import 'focus_outline.dart';

class MerchantNavigation extends StatelessWidget {
  const MerchantNavigation({
    this.rail = false,
    this.extended = false,
    super.key,
  });
  final bool rail, extended;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final path = GoRouterState.of(context).uri.path;
    final routes = extended
        ? [
            '/',
            '/debts',
            '/chat',
            '/weekly',
            '/forecast',
            '/flags',
            '/import',
            '/sample',
          ]
        : ['/', '/debts', '/chat', 'more'];
    final labels = extended
        ? [
            l.todayTitle,
            l.debtsTitle,
            l.navChat,
            l.weeklyTitle,
            l.forecastTitle,
            l.flagsTitle,
            l.importTitle,
            l.sampleTitle,
          ]
        : [l.todayTitle, l.debtsTitle, l.navChat, l.more];
    const outlined = [
      Icons.today_outlined,
      Icons.people_outline,
      Icons.chat_bubble_outline,
      Icons.date_range_outlined,
      Icons.show_chart_outlined,
      Icons.flag_outlined,
      Icons.upload_file_outlined,
      Icons.storefront_outlined,
    ];
    const filled = [
      Icons.today,
      Icons.people,
      Icons.chat_bubble,
      Icons.date_range,
      Icons.show_chart,
      Icons.flag,
      Icons.upload_file,
      Icons.storefront,
    ];
    final found = routes.indexOf(path);
    final selected = found >= 0
        ? found
        : extended
        ? 0
        : 3;
    void choose(int i) {
      if (routes[i] == 'more') {
        showMerchantMenu(context);
        return;
      }
      if (i < 3) {
        context.go(routes[i]);
      } else {
        context.push(routes[i]);
      }
    }

    if (!rail) {
      return DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            top: BorderSide(color: Theme.of(context).colorScheme.outline),
          ),
        ),
        child: NavigationBar(
          animationDuration: AppMotion.state(context),
          selectedIndex: selected,
          onDestinationSelected: choose,
          destinations: [
            for (var i = 0; i < routes.length; i++)
              NavigationDestination(
                icon: Icon(i == 3 ? Icons.more_horiz : outlined[i]),
                selectedIcon: Icon(i == 3 ? Icons.more_horiz : filled[i]),
                label: labels[i],
                tooltip: labels[i],
              ),
          ],
        ),
      );
    }
    final height = MediaQuery.sizeOf(context).height;
    final minimum =
        MediaQuery.textScalerOf(context).scale(AppDimens.navigationHeight) *
            routes.length +
        (extended ? AppDimens.toolbarHeight + AppDimens.xl : AppDimens.lg);
    return DecoratedBox(
      decoration: BoxDecoration(
        border: BorderDirectional(
          end: BorderSide(color: Theme.of(context).colorScheme.outline),
        ),
      ),
      child: SingleChildScrollView(
        child: SizedBox(
          width: extended ? AppDimens.railWidth : AppDimens.mediumRailWidth,
          height: height > minimum ? height : minimum,
          child: NavigationRail(
            extended: extended,
            minExtendedWidth: AppDimens.railWidth,
            minWidth: AppDimens.mediumRailWidth,
            groupAlignment: -1,
            labelType: extended
                ? NavigationRailLabelType.none
                : NavigationRailLabelType.all,
            leading: extended
                ? Padding(
                    padding: const EdgeInsets.all(AppDimens.lg),
                    child: Text(
                      l.appTitle,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  )
                : null,
            selectedIndex: selected,
            onDestinationSelected: choose,
            destinations: [
              for (var i = 0; i < routes.length; i++)
                NavigationRailDestination(
                  padding: EdgeInsets.only(
                    top: AppDimens.xs + (extended && i == 3 ? AppDimens.xl : 0),
                    bottom: AppDimens.xs,
                  ),
                  icon: Icon(
                    !extended && i == 3 ? Icons.more_horiz : outlined[i],
                  ),
                  selectedIcon: Icon(
                    !extended && i == 3 ? Icons.more_horiz : filled[i],
                  ),
                  label: Text(
                    labels[i],
                    maxLines: extended ? 2 : 1,
                    softWrap: extended,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

Future<void> showMerchantMenu(BuildContext context) async {
  final l = AppLocalizations.of(context);
  final router = GoRouter.of(context);
  final route = await showModalBottomSheet<String>(
    context: context,
    isScrollControlled: true,
    sheetAnimationStyle: const AnimationStyle(
      duration: Duration.zero,
      reverseDuration: Duration.zero,
    ),
    builder: (context) => SoftEntrance(
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppDimens.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      l.more,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  IconButton(
                    tooltip: l.dismiss,
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.close_outlined),
                  ),
                ],
              ),
              for (final item in [
                ('/weekly', l.weeklyTitle, Icons.date_range_outlined),
                ('/forecast', l.forecastTitle, Icons.show_chart_outlined),
                ('/flags', l.flagsTitle, Icons.flag_outlined),
                ('/import', l.importTitle, Icons.upload_file_outlined),
                ('/sample', l.sampleTitle, Icons.storefront_outlined),
              ])
                FocusOutline(
                  child: ListTile(
                    leading: Icon(item.$3),
                    title: Text(item.$2),
                    onTap: () => Navigator.pop(context, item.$1),
                  ),
                ),
            ],
          ),
        ),
      ),
    ),
  );
  if (route != null && context.mounted) {
    router.push(route);
  }
}
