import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_theme.dart';
import '../core/widgets/focus_outline.dart';
import '../l10n/generated/app_localizations.dart';
import 'di/injection.dart';

class ShgadApp extends StatelessWidget {
  const ShgadApp({super.key, this.locale = const Locale('ar'), this.textScale});

  final Locale locale;
  final double? textScale;

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      onGenerateTitle: (context) => AppLocalizations.of(context).appTitle,
      locale: locale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      theme: AppTheme.light,
      builder: (context, child) => _RouteTitle(
        child: MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: textScale == null
                ? MediaQuery.textScalerOf(context)
                : TextScaler.linear(textScale!),
          ),
          child: Theme(
            data: AppTheme.withMotion(context, Theme.of(context)),
            child: KeyboardFocusLayer(child: child!),
          ),
        ),
      ),
      routerConfig: getIt<GoRouter>(),
    );
  }
}

class _RouteTitle extends StatefulWidget {
  const _RouteTitle({required this.child});
  final Widget child;
  @override
  State<_RouteTitle> createState() => _RouteTitleState();
}

class _RouteTitleState extends State<_RouteTitle> {
  final router = getIt<GoRouter>();
  bool scheduled = false;
  @override
  void initState() {
    super.initState();
    router.routerDelegate.addListener(changed);
  }

  void changed() {
    if (scheduled || !mounted) return;
    scheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      scheduled = false;
      if (mounted) setState(() {});
    });
    WidgetsBinding.instance.scheduleFrame();
  }

  @override
  void dispose() {
    router.routerDelegate.removeListener(changed);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Title(
    title: _routeTitle(
      AppLocalizations.of(context),
      router.routerDelegate.currentConfiguration.isEmpty
          ? '/'
          : router.state.uri.path,
    ),
    color: Theme.of(context).colorScheme.primary,
    child: widget.child,
  );
}

String _routeTitle(AppLocalizations l, String path) => switch (path) {
  '/' => l.todayTitle,
  '/debts' => l.debtsTitle,
  '/chat' => l.chatTitle,
  '/entry' => l.entryTitle,
  '/close' => l.closeTitle,
  '/evidence' => l.evidence,
  '/weekly' => l.weeklyTitle,
  '/forecast' => l.forecastTitle,
  '/sample' => l.sampleTitle,
  '/import' => l.importTitle,
  '/flags' => l.flagsTitle,
  '/gallery' => l.galleryTitle,
  _ => l.appTitle,
};
