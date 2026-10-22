import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'package:shgad/core/domain/amount.dart';
import 'package:shgad/core/widgets/gallery_page.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'support/test_app.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final loader = FontLoader('Cairo')
      ..addFont(rootBundle.load('assets/fonts/Cairo.ttf'));
    await loader.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });
  for (final locale in ['ar', 'en']) {
    testWidgets('Narrow localized hero golden $locale', (tester) async {
      tester.view.physicalSize = const Size(320, 400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          locale: Locale(locale),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(1.3)),
            child: child!,
          ),
          home: Scaffold(
            body: SingleChildScrollView(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: RepaintBoundary(
                  key: const ValueKey('narrow_hero'),
                  child: Builder(
                    builder: (context) => HeroCard(
                      amount: const Amount(
                        value: 420000,
                        kind: 'verified',
                        label: 'cash_on_hand',
                        sources: [],
                        formula: '',
                      ),
                      label: AppLocalizations.of(context).cashOnHand,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await expectLater(
        find.byKey(const ValueKey('narrow_hero')),
        matchesGoldenFile('goldens/hero-320-$locale-1.3.png'),
      );
      expect(tester.takeException(), isNull);
    });
  }
  for (final config in [(360.0, 1.0), (360.0, 1.3), (1280.0, 1.0)]) {
    final (width, scale) = config;
    final suffix = '${width.toInt()}-ar-$scale';
    testWidgets('Every shared component golden $suffix', (tester) async {
      tester.view.physicalSize = Size(width, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(scale)),
            child: child!,
          ),
          home: const GalleryPage(),
        ),
      );
      await tester.pumpAndSettle();
      for (final id in [
        'hero',
        'ledger',
        'pills',
        'actions',
        'text_action',
        'number',
        'empty',
        'field',
        'date',
        'choice',
        'segment',
        'strip',
        'error',
        'offline',
        'progress',
        'chat',
        'composer',
        'field_error',
        'meta',
        'evidence',
      ]) {
        final specimen = find.byKey(ValueKey('gallery_$id'));
        await tester.ensureVisible(specimen);
        await tester.pumpAndSettle();
        await expectLater(
          specimen,
          matchesGoldenFile('goldens/components/$id-$suffix.png'),
        );
        expect(tester.takeException(), isNull);
      }
    });
    testWidgets('Today and responsive shell golden $suffix', (tester) async {
      installRecordedApp();
      addTearDown(() => getIt.reset());
      tester.view.physicalSize = Size(width, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        RepaintBoundary(
          key: const ValueKey('app_golden'),
          child: ShgadApp(textScale: scale),
        ),
      );
      await tester.pumpAndSettle();
      await expectLater(
        find.byKey(const ValueKey('app_golden')),
        matchesGoldenFile('goldens/today-shell-$suffix.png'),
      );
      expect(tester.takeException(), isNull);
    });
  }
  for (final state in [
    'hover',
    'focus',
    'pressed',
    'disabled',
    'loading',
    'error',
    'offline',
  ]) {
    testWidgets('Interactive component state goldens $state', (tester) async {
      tester.view.physicalSize = const Size(360, 2400);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light,
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: GalleryPage(initialState: state),
        ),
      );
      await tester.pump(const Duration(milliseconds: 300));
      for (final id in [
        'actions',
        'field',
        'choice',
        'segment',
        'field_error',
        'progress',
        'offline',
      ]) {
        final specimen = find.byKey(ValueKey('gallery_$id'));
        await tester.ensureVisible(specimen);
        await tester.pump(const Duration(milliseconds: 200));
        await expectLater(
          specimen,
          matchesGoldenFile('goldens/states/$id-$state.png'),
        );
        expect(tester.takeException(), isNull);
      }
    });
  }
}
