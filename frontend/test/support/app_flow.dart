import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/core/widgets/merchant_page.dart';
import 'package:shgad/features/chat/presentation/bloc/chat_bloc.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'test_app.dart';

void registerAppFlow() {
  testWidgets('sample shop → chat → source evidence → three scenarios → reset', (
    tester,
  ) async {
    final api = installRecordedApp();
    addTearDown(() => getIt.reset());
    await tester.pumpWidget(const ShgadApp(locale: Locale('ar')));
    await tester.pumpAndSettle();
    final l = AppLocalizations.of(tester.element(find.byType(Navigator).first));
    Future<void> tap(Finder target) async {
      await tester.ensureVisible(target);
      await tester.pumpAndSettle();
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    Future<void> more(String item) async {
      await tap(find.text(l.more));
      await tap(find.text(item).last);
    }

    await more(l.sampleTitle);
    expect(find.text(l.fictionalShop), findsOneWidget);
    await tap(find.byKey(const ValueKey('sample_prepare')));
    expect(api.requests.where((r) => r.path == '/api/demo/reset'), isEmpty);
    await tap(find.byKey(const ValueKey('sample_confirm')));
    expect(find.text(l.sampleReady), findsOneWidget);
    await tap(find.text(l.openToday));
    final navigation = find.byType(MerchantNavigation);
    expect(
      find.descendant(of: navigation, matching: find.text(l.debtsTitle)),
      findsOneWidget,
    );
    await tap(
      find.descendant(of: navigation, matching: find.text(l.chatTitle)),
    );
    await tap(find.text(l.promptSupplier));
    await tap(find.byKey(const ValueKey('chat_send')));
    for (
      var attempt = 0;
      attempt < 100 && getIt<ChatBloc>().state.view.turns.isEmpty;
      attempt++
    ) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(
      getIt<ChatBloc>().state.view.turns,
      hasLength(1),
      reason:
          '${getIt<ChatBloc>().state.runtimeType}; API: ${api.requests.map((r) => r.path).join(', ')}',
    );
    final cash = find.byWidgetPredicate(
      (w) => w is AmountView && w.amount.label == 'cash_on_hand',
    );
    await tap(find.descendant(of: cash, matching: find.text(l.cashOnHand)));
    expect(find.text('CNT-090'), findsOneWidget);
    expect(api.requests.any((r) => r.path == '/api/evidence/sources'), isTrue);
    await tap(find.byTooltip(l.dismiss));
    await more(l.forecastTitle);
    for (final label in [
      l.scenarioConservative,
      l.scenarioStress,
      l.scenarioBase,
    ]) {
      await tap(find.text(label));
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
    await more(l.sampleTitle);
    await tap(find.byKey(const ValueKey('sample_prepare')));
    await tap(find.byKey(const ValueKey('sample_confirm')));
    expect(
      api.requests.where((r) => r.path == '/api/demo/reset'),
      hasLength(2),
    );
    expect(getIt<ChatBloc>().state.view.turns, isEmpty);
    expect(tester.takeException(), isNull);
  });
}
