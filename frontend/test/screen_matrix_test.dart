import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/features/chat/presentation/bloc/chat_bloc.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'support/fixtures.dart';
import 'support/test_app.dart';

void main() {
  setUp(installRecordedApp);
  tearDown(() => getIt.reset());
  for (final locale in ['ar', 'en']) {
    for (final width in [320.0, 360.0]) {
      for (final scale in [1.0, 1.3]) {
        for (final route in [
          '/',
          '/debts',
          '/entry',
          '/close',
          '/chat',
          '/evidence?ids=ENT-ORIGINAL,CAT-01&formula=source%20rows',
          '/weekly',
          '/forecast',
          '/sample',
          '/import',
          '/flags',
          '/gallery',
        ]) {
          testWidgets('$route $locale ${width}px scale $scale', (tester) async {
            tester.view.physicalSize = Size(width, 800);
            tester.view.devicePixelRatio = 1;
            addTearDown(tester.view.resetPhysicalSize);
            addTearDown(tester.view.resetDevicePixelRatio);
            getIt<GoRouter>().go(route);
            await tester.pumpWidget(
              ShgadApp(locale: Locale(locale), textScale: scale),
            );
            await tester.pumpAndSettle();
            final l = AppLocalizations.of(
              tester.element(find.byType(Navigator).first),
            );
            if (route == '/chat') {
              await tester.enterText(
                find.byKey(const ValueKey('chat_input')),
                l.promptSupplier,
              );
              await tester.pump();
              await tester.tap(find.byKey(const ValueKey('chat_send')));
              await tester.pumpAndSettle();
              expect(
                find.text(chatJson()['reply_ar'] as String),
                findsOneWidget,
              );
              expect(
                getIt<ChatBloc>()
                    .state
                    .view
                    .turns
                    .single
                    .reply
                    .resolved!
                    .partyId,
                'CUST-01',
              );
            } else if (route == '/forecast') {
              for (final label in [
                l.scenarioConservative,
                l.scenarioStress,
                l.scenarioBase,
              ]) {
                await tester.tap(find.text(label));
                await tester.pumpAndSettle();
                expect(
                  tester
                      .widget<ChoiceChip>(
                        find.ancestor(
                          of: find.text(label),
                          matching: find.byType(ChoiceChip),
                        ),
                      )
                      .selected,
                  isTrue,
                );
              }
              expect(find.byType(CustomPaint), findsWidgets);
              await tester.scrollUntilVisible(
                find.text(l.estimateOnly),
                200,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              expect(find.text(l.estimateOnly), findsOneWidget);
            } else if (route == '/close') {
              await tester.scrollUntilVisible(
                find.text(l.neutralDifference),
                250,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              expect(find.text(l.neutralDifference), findsOneWidget);
              await tester.scrollUntilVisible(
                find.byKey(const ValueKey('resolution_false')),
                250,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              final dropdown = find
                  .byType(DropdownButtonFormField<String>)
                  .first;
              expect(
                tester
                    .widget<DropdownButtonFormField<String>>(dropdown)
                    .initialValue,
                isNull,
              );
            } else if (route == '/import') {
              await tester.tap(find.byKey(const ValueKey('csv_pick')));
              await tester.pumpAndSettle();
              expect(find.text('fictional.csv'), findsOneWidget);
              await tester.scrollUntilVisible(
                find.byType(CheckboxListTile),
                200,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              await tester.tap(find.byType(CheckboxListTile));
              await tester.pumpAndSettle();
              await tester.scrollUntilVisible(
                find.byKey(const ValueKey('csv_preview')),
                250,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              await tester.tap(find.byKey(const ValueKey('csv_preview')));
              await tester.pumpAndSettle();
              await tester.scrollUntilVisible(
                find.text(l.previewFiveRows),
                250,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              expect(find.text(l.previewFiveRows), findsOneWidget);
            } else if (route == '/sample') {
              expect(find.text(l.fictionalShop), findsOneWidget);
              await tester.scrollUntilVisible(
                find.byKey(const ValueKey('sample_prepare')),
                200,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              await tester.tap(find.byKey(const ValueKey('sample_prepare')));
              await tester.pumpAndSettle();
              await tester.scrollUntilVisible(
                find.text(l.resetWarning),
                200,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pumpAndSettle();
              expect(find.text(l.resetWarning), findsOneWidget);
            } else if (route.startsWith('/evidence')) {
              expect(find.text(l.voidReasonValue('mistyped')), findsOneWidget);
              final amounts = tester.widgetList<AmountView>(
                find.byType(AmountView),
              );
              expect(amounts.any((a) => a.voided), isTrue);
            } else if (route == '/weekly') {
              expect(find.text(l.unexplainedDifference), findsOneWidget);
            } else if (route == '/flags') {
              expect(find.text(l.flagDuplicate), findsWidgets);
            } else if (route == '/entry') {
              expect(find.byKey(const ValueKey('amount_iqd')), findsOneWidget);
            } else if (route == '/debts') {
              expect(find.byType(ExpansionTile), findsWidgets);
            } else if (route == '/') {
              expect(find.text(l.cashOnHand), findsOneWidget);
            }
            expect(tester.takeException(), isNull);
          });
        }
      }
    }
  }
}
