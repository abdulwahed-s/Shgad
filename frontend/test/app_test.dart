import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/widgets/chat_bubble.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';

void main() {
  setUp(configureDependencies);
  tearDown(() async => getIt.reset());

  for (final locale in [const Locale('ar'), const Locale('en')]) {
    for (final scale in [1.0, 1.3]) {
      testWidgets('${locale.languageCode} phone shell at text scale $scale', (
        tester,
      ) async {
        tester.view.physicalSize = const Size(360, 800);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

        await tester.pumpWidget(ShgadApp(locale: locale));
        await tester.pumpAndSettle();

        final context = tester.element(find.byType(ChatBubble));
        final l10n = AppLocalizations.of(context);
        expect(find.text(l10n.appTitle), findsOneWidget);
        expect(find.text(l10n.chatTitle), findsOneWidget);
        expect(find.text(l10n.chatSetupNotice), findsOneWidget);
        expect(
          Directionality.of(context),
          locale.languageCode == 'ar' ? TextDirection.rtl : TextDirection.ltr,
        );
        expect(tester.takeException(), isNull);
      });
    }
  }
}
