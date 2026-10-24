import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/network/connectivity.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'support/test_app.dart';

void main() {
  late RecordedApi api;
  setUp(() => api = installRecordedApp());
  tearDown(() => getIt.reset());

  testWidgets(
    'Difference-review draft survives an offline rebuild and save stays disabled',
    (tester) async {
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      getIt<GoRouter>().go('/close');
      final semantics = tester.ensureSemantics();
      try {
        await tester.pumpWidget(const ShgadApp(locale: Locale('en')));
        await tester.pumpAndSettle();
        final note = find.byKey(const ValueKey('resolution_note'));
        await tester.scrollUntilVisible(
          note,
          300,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.pumpAndSettle();
        await tester.enterText(note, 'fictional review draft');
        await tester.pumpAndSettle();
        final accessibleFieldId = tester.getSemantics(note).id;
        String visibleDraft() => tester
            .widget<EditableText>(
              find.descendant(of: note, matching: find.byType(EditableText)),
            )
            .controller
            .text;
        getIt<ConnectionSource>().set(false);
        await tester.pumpAndSettle();
        expect(visibleDraft(), 'fictional review draft');
        expect(tester.getSemantics(note).id, accessibleFieldId);
        final review = find.widgetWithText(
          PrimaryButton,
          'Review before saving',
        );
        expect(tester.widget<PrimaryButton>(review).onPressed, isNull);
        getIt<ConnectionSource>().set(true);
        await tester.pumpAndSettle();
        expect(visibleDraft(), 'fictional review draft');
        expect(
          api.requests.where((request) => request.method == 'POST'),
          isEmpty,
        );
      } finally {
        semantics.dispose();
      }
    },
  );
}
