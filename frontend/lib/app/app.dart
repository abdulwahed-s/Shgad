import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_theme.dart';
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
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(
          textScaler: textScale == null
              ? MediaQuery.textScalerOf(context)
              : TextScaler.linear(textScale!),
        ),
        child: child!,
      ),
      routerConfig: getIt<GoRouter>(),
    );
  }
}
