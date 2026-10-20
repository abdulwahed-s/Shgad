import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/widgets/gallery_page.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';

void main() {
  for (final language in ['ar', 'en']) {
    for (final scale in [1.0, 1.3]) {
      testWidgets('Gallery $language 360px scale $scale', (tester) async {
        tester.view.physicalSize = const Size(360, 800);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(
          MaterialApp(
            locale: Locale(language),
            theme: AppTheme.light,
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
        expect(
          Directionality.of(tester.element(find.byType(AmountView).first)),
          language == 'ar' ? TextDirection.rtl : TextDirection.ltr,
        );
        await tester.tap(find.byType(AmountView).first);
        await tester.pumpAndSettle();
        expect(find.byType(EvidenceSheet), findsOneWidget);
        expect(find.text('GALLERY-CNT'), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    }
  }
}
