import 'dart:ui' show SemanticsAction, SemanticsActionEvent, Tristate;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/domain/amount.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/core/widgets/page_header.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';

const amount = Amount(
  value: 404500,
  kind: 'verified',
  label: 'cash_on_hand',
  sources: [],
  formula: '',
);
Widget host(
  Widget child, {
  double width = 320,
  double scale = 1.3,
  String locale = 'ar',
}) => MaterialApp(
  theme: AppTheme.light,
  locale: Locale(locale),
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  home: MediaQuery(
    data: MediaQueryData(
      size: Size(width, 800),
      textScaler: TextScaler.linear(scale),
    ),
    child: Scaffold(
      body: Align(
        alignment: Alignment.topCenter,
        child: SizedBox(width: width, child: child),
      ),
    ),
  ),
);

void main() {
  setUpAll(() async {
    final loader = FontLoader('Cairo')
      ..addFont(rootBundle.load('assets/fonts/Cairo.ttf'));
    await loader.load();
  });
  testWidgets('Selectable captions include their full48px pointer region', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    String? copied;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = (call.arguments as Map)['text'] as String;
        }
        return null;
      },
    );
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        null,
      ),
    );
    await tester.pumpWidget(host(const SelectableCaption('SOURCE-01')));
    await tester.pumpAndSettle();
    final editable = find.byType(EditableText);
    final data = tester
        .getSemantics(find.byType(SelectableCaption))
        .getSemanticsData();
    expect(data.label, contains('SOURCE-01'));
    expect(data.flagsCollection.isEnabled, isNot(Tristate.isFalse));
    expect(data.flagsCollection.isTextField, isFalse);
    final render = tester.state<EditableTextState>(editable).renderEditable;
    expect(render.size.height, greaterThanOrEqualTo(48));
    final rect = tester.getRect(editable);
    for (final point in [
      Offset(rect.center.dx, rect.top + 2),
      Offset(rect.center.dx, rect.bottom - 2),
    ]) {
      tester.widget<EditableText>(editable).focusNode.unfocus();
      await tester.pumpAndSettle();
      await tester.tapAt(point);
      await tester.pumpAndSettle();
      expect(tester.widget<EditableText>(editable).focusNode.hasFocus, isTrue);
    }
    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.keyA);
    await tester.sendKeyEvent(LogicalKeyboardKey.keyC);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pumpAndSettle();
    expect(copied, 'SOURCE-01');
    semantics.dispose();
  });
  testWidgets('Overflow actions stack at full width with the token gap', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        ActionGroup(
          children: [
            PrimaryButton(
              text: 'A deliberately long primary action',
              onPressed: () {},
            ),
            SecondaryButton(text: 'Edit', onPressed: () {}),
          ],
        ),
      ),
    );
    await tester.pumpAndSettle();
    final first = tester.getRect(find.byType(FilledButton));
    final second = tester.getRect(find.byType(OutlinedButton));
    expect(first.width, 320);
    expect(second.width, 320);
    expect(second.top - first.bottom, 12);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
    'Ledger label and amount share a row unless amount exceeds55 percent',
    (tester) async {
      await tester.pumpWidget(
        host(
          const LedgerRow(amount: amount, label: 'label'),
          width: 560,
          scale: 1,
        ),
      );
      await tester.pumpAndSettle();
      final label = tester.getTopLeft(find.text('label'));
      final value = tester.getTopLeft(find.text('٤٠٤٬٥٠٠ دينار'));
      expect((label.dy - value.dy).abs(), lessThan(4));
      await tester.pumpWidget(
        host(const LedgerRow(amount: amount, label: 'label'), width: 180),
      );
      await tester.pumpAndSettle();
      expect(
        tester.getTopLeft(find.text('٤٠٤٬٥٠٠ دينار')).dy,
        greaterThan(tester.getBottomLeft(find.text('label')).dy),
      );
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets('Hero unit wraps without shrinking or truncating exact digits', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        const AmountView(amount: amount, label: 'label', hero: true),
        width: 170,
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('٤٠٤٬٥٠٠'), findsOneWidget);
    expect(find.text('دينار'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('دينار')).dy,
      greaterThan(tester.getTopLeft(find.text('٤٠٤٬٥٠٠')).dy),
    );
    expect(tester.takeException(), isNull);
  });
  testWidgets('English compact hero keeps the full multi-word unit readable', (
    tester,
  ) async {
    await tester.pumpWidget(
      host(
        const HeroCard(
          amount: Amount(
            value: 420000,
            kind: 'verified',
            label: 'cash_on_hand',
            sources: [],
            formula: '',
          ),
          label: 'Cash on hand',
        ),
        locale: 'en',
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('420'), findsOneWidget);
    expect(find.text('thousand IQD'), findsOneWidget);
    final card = tester.getRect(find.byType(HeroCard));
    for (final text in ['420', 'thousand IQD']) {
      final bounds = tester.getRect(find.text(text));
      expect(bounds.left, greaterThanOrEqualTo(card.left));
      expect(bounds.right, lessThanOrEqualTo(card.right));
    }
    expect(tester.takeException(), isNull);
  });
  testWidgets('Metadata wraps as captions without a detached separator', (
    tester,
  ) async {
    const updated = 'Last updated: 28 September, 10:00';
    const date = 'Business date: 28 September';
    const meta = PageMeta(updated: updated, date: date);
    await tester.pumpWidget(host(meta, locale: 'en'));
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text(date)).dy,
      greaterThan(tester.getBottomLeft(find.text(updated)).dy),
    );
    expect(
      find.byWidgetPredicate(
        (widget) =>
            widget is Container &&
            widget.decoration is BoxDecoration &&
            (widget.decoration! as BoxDecoration).shape == BoxShape.circle,
      ),
      findsNothing,
    );
    await tester.pumpWidget(host(meta, width: 760, scale: 1, locale: 'en'));
    await tester.pumpAndSettle();
    expect(
      tester.getTopLeft(find.text(date)).dy,
      tester.getTopLeft(find.text(updated)).dy,
    );
    expect(tester.takeException(), isNull);
  });
  testWidgets('Amount semantics joins label exact value status and time', (
    tester,
  ) async {
    final handle = tester.ensureSemantics();
    var taps = 0;
    await tester.pumpWidget(
      host(
        AmountView(
          amount: amount,
          label: 'cash',
          caption: 'count time',
          onTap: () => taps++,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(
      find.bySemanticsLabel('cash, ٤٠٤٬٥٠٠ دينار, مؤكد, count time'),
      findsOneWidget,
    );
    expect(
      tester.getSize(find.byType(InkWell).first).height,
      greaterThanOrEqualTo(48),
    );
    final node = tester.getSemantics(find.byType(AmountView));
    expect(node.getSemanticsData().hasAction(SemanticsAction.tap), isTrue);
    tester.binding.performSemanticsAction(
      SemanticsActionEvent(
        type: SemanticsAction.tap,
        nodeId: node.id,
        viewId: tester.view.viewId,
      ),
    );
    await tester.pump();
    expect(
      taps,
      1,
      reason: 'Screen-reader activation must open the same evidence',
    );
    handle.dispose();
  });
}
