import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'support/test_app.dart';

void main() {
  setUp(installRecordedApp);
  tearDown(() => getIt.reset());
  testWidgets(
    'The visible entry date follows server setup and a new entry clears old input',
    (tester) async {
      getIt<GoRouter>().go('/entry');
      await tester.pumpWidget(const ShgadApp(locale: Locale('en')));
      await tester.pumpAndSettle();
      String visible(String key) => tester
          .widget<EditableText>(
            find.descendant(
              of: find.byKey(ValueKey(key)),
              matching: find.byType(EditableText),
            ),
          )
          .controller
          .text;
      expect(visible('business_date'), '2026-09-28');
      await tester.enterText(find.byKey(const ValueKey('amount_iqd')), '12000');
      await tester.tap(find.byKey(const ValueKey('entry_review')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('entry_save')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('New entry'));
      await tester.pumpAndSettle();
      expect(visible('business_date'), '2026-09-28');
      expect(visible('amount_iqd'), isEmpty);
    },
  );
}
