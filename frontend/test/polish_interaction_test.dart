import 'dart:convert';
import 'package:dio/dio.dart';
import 'dart:ui' show PointerDeviceKind, ImageByteFormat;
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'package:shgad/core/domain/amount.dart';
import 'package:shgad/core/widgets/chat_composer.dart';
import 'package:shgad/core/widgets/form_fields.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'package:shgad/features/quick_entry/presentation/bloc/entry_bloc.dart';
import 'package:shgad/features/quick_entry/presentation/pages/entry_page.dart';
import 'support/test_app.dart';
import 'support/fixtures.dart';
import 'core_test.dart' show WireAdapter;

Widget localized(Widget child, {bool reduced = false}) => MaterialApp(
  theme: AppTheme.light,
  locale: const Locale('ar'),
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  builder: (context, child) => MediaQuery(
    data: MediaQuery.of(context).copyWith(disableAnimations: reduced),
    child: Builder(
      builder: (context) => Theme(
        data: AppTheme.withMotion(context, Theme.of(context)),
        child: child!,
      ),
    ),
  ),
  home: Scaffold(
    body: Padding(padding: const EdgeInsets.all(16), child: child),
  ),
);

Future<List<int>> pixels(WidgetTester tester, Finder target) async =>
    (await tester.runAsync(() async {
      final image = await tester
          .renderObject<RenderRepaintBoundary>(target)
          .toImage();
      final data = await image.toByteData(format: ImageByteFormat.rawRgba);
      final result = data!.buffer.asUint8List().toList();
      image.dispose();
      return result;
    }))!;

void main() {
  setUpAll(() async {
    for (final font in [
      ('Cairo', 'assets/fonts/Cairo.ttf'),
      ('MaterialIcons', 'fonts/MaterialIcons-Regular.otf'),
    ]) {
      final loader = FontLoader(font.$1)..addFont(rootBundle.load(font.$2));
      await loader.load();
    }
  });
  testWidgets('Narrow Arabic title renders every glyph without an ellipsis', (
    tester,
  ) async {
    installRecordedApp();
    addTearDown(() => getIt.reset());
    tester.view.physicalSize = const Size(320, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    getIt<GoRouter>().go('/import');
    await tester.pumpWidget(const ShgadApp(textScale: 1.3));
    await tester.pumpAndSettle();
    final l = AppLocalizations.of(tester.element(find.byType(AppBar)));
    final title = find.descendant(
      of: find.byType(AppBar),
      matching: find.text(l.importTitle),
    );
    final paragraph = tester.renderObject<RenderParagraph>(title);
    expect(paragraph.didExceedMaxLines, isFalse);
    final glyphs = paragraph.getBoxesForSelection(
      TextSelection(baseOffset: 0, extentOffset: l.importTitle.length),
    );
    expect(glyphs, isNotEmpty);
    final header = tester.getRect(find.byType(AppBar));
    final origin = paragraph.localToGlobal(Offset.zero);
    for (final box in glyphs) {
      expect(origin.dx + box.left, greaterThanOrEqualTo(header.left));
      expect(origin.dx + box.right, lessThanOrEqualTo(header.right));
      expect(origin.dy + box.bottom, lessThanOrEqualTo(header.bottom));
    }
    expect(tester.takeException(), isNull);
  });
  for (final width in [360.0, 768.0, 1280.0]) {
    testWidgets('Navigation keeps selected destination at $width', (
      tester,
    ) async {
      installRecordedApp();
      addTearDown(() => getIt.reset());
      tester.view.physicalSize = Size(width, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const ShgadApp());
      await tester.pumpAndSettle();
      final nav = width < 600
          ? find.byType(NavigationBar)
          : find.byType(NavigationRail);
      final l = AppLocalizations.of(tester.element(nav));
      await tester.tap(
        find.descendant(of: nav, matching: find.text(l.debtsTitle)),
      );
      await tester.pumpAndSettle();
      expect(
        getIt<GoRouter>().routeInformationProvider.value.uri.path,
        '/debts',
      );
      expect(
        width < 600
            ? tester.widget<NavigationBar>(nav).selectedIndex
            : tester.widget<NavigationRail>(nav).selectedIndex,
        1,
      );
      if (width >= 1024) {
        expect(tester.widget<NavigationRail>(nav).extended, isTrue);
      }
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets(
    'Tab titles follow modal evidence, gallery and push/pop restoration',
    (tester) async {
      installRecordedApp();
      addTearDown(() => getIt.reset());
      getIt<GoRouter>().go('/chat');
      await tester.pumpWidget(const ShgadApp());
      await tester.pumpAndSettle();
      final l = AppLocalizations.of(
        tester.element(find.byType(Navigator).first),
      );
      String title() => tester.widgetList<Title>(find.byType(Title)).last.title;
      expect(title(), l.chatTitle);
      getIt<GoRouter>().push('/evidence?ids=CNT-090');
      await tester.pumpAndSettle();
      expect(title(), l.evidence);
      getIt<GoRouter>().pop();
      await tester.pumpAndSettle();
      expect(title(), l.chatTitle);
      getIt<GoRouter>().go('/gallery');
      await tester.pumpAndSettle();
      expect(title(), l.galleryTitle);
    },
  );
  testWidgets(
    'More sheet supports Escape, task back and hidden compact navigation',
    (tester) async {
      installRecordedApp();
      addTearDown(() => getIt.reset());
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const ShgadApp());
      await tester.pumpAndSettle();
      final l = AppLocalizations.of(tester.element(find.byType(NavigationBar)));
      await tester.tap(find.text(l.more));
      await tester.pumpAndSettle();
      expect(find.byType(BottomSheet), findsOneWidget);
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();
      expect(find.byType(BottomSheet), findsNothing);
      await tester.tap(find.text(l.more));
      await tester.pumpAndSettle();
      await tester.tap(find.text(l.importTitle));
      await tester.pumpAndSettle();
      expect(getIt<GoRouter>().state.uri.path, '/import');
      expect(find.byType(NavigationBar), findsNothing);
      await tester.tap(find.byType(BackButton));
      await tester.pumpAndSettle();
      expect(getIt<GoRouter>().routeInformationProvider.value.uri.path, '/');
      expect(find.byType(NavigationBar), findsOneWidget);
    },
  );
  testWidgets(
    'Reset connection failure is visible inside confirmation and can retry',
    (tester) async {
      final api = installRecordedApp();
      addTearDown(() => getIt.reset());
      getIt<GoRouter>().go('/sample');
      await tester.pumpWidget(const ShgadApp());
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.byKey(const ValueKey('sample_prepare')));
      await tester.tap(find.byKey(const ValueKey('sample_prepare')));
      await tester.pumpAndSettle();
      api.offline = true;
      await tester.tap(find.byKey(const ValueKey('sample_confirm')));
      await tester.pumpAndSettle();
      final dialog = find.byType(AlertDialog);
      final l = AppLocalizations.of(tester.element(dialog));
      expect(
        find.descendant(of: dialog, matching: find.text(l.needsConnection)),
        findsOneWidget,
      );
      expect(
        tester
            .widget<PrimaryButton>(find.byKey(const ValueKey('sample_confirm')))
            .onPressed,
        isNull,
      );
      api.offline = false;
      await tester.tap(
        find.descendant(of: dialog, matching: find.text(l.retry)),
      );
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<PrimaryButton>(find.byKey(const ValueKey('sample_confirm')))
            .onPressed,
        isNotNull,
      );
    },
  );
  testWidgets('Missing daily count preserves saved source and undo after refresh', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = installRecordedApp();
    addTearDown(() => getIt.reset());
    var countSaved = false;
    getIt<Dio>().httpClientAdapter = WireAdapter((request) async {
      if (request.path == '/api/entries') countSaved = true;
      if (request.path.startsWith('/api/entries/') &&
          request.path.endsWith('/void')) {
        countSaved = false;
      }
      if (request.path.startsWith('/api/daily-close/')) {
        // Render the real loading frame, which inserts progress above the form.
        await Future<void>.delayed(const Duration(milliseconds: 150));
        final body = closeJson();
        if (!countSaved) {
          body['count'] = {
            ...body['count'] as Map,
            'amount_iqd': null,
            'kind': 'missing',
          };
        }
        return ResponseBody.fromString(
          jsonEncode(body),
          200,
          headers: {
            'content-type': ['application/json'],
          },
        );
      }
      return api.respond(request);
    });
    getIt<GoRouter>().go('/close');
    await tester.pumpWidget(const ShgadApp(textScale: 1.3));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('amount_iqd')), findsOneWidget);
    expect(find.byType(RadioGroup<String>), findsNothing);
    expect(find.byType(PrimaryButton), findsOneWidget);
    await tester.enterText(find.byKey(const ValueKey('amount_iqd')), '420000');
    await tester.pumpAndSettle();
    final l = AppLocalizations.of(tester.element(find.byType(PrimaryButton)));
    final entryBloc = tester
        .element(find.byKey(const ValueKey('amount_iqd')))
        .read<EntryBloc>();
    final review = find.text(l.reviewEntry);
    await tester.ensureVisible(review);
    await tester.pumpAndSettle();
    await tester.tap(review);
    await tester.pumpAndSettle();
    expect(countSaved, isFalse);
    expect(
      entryBloc.state.view.mode,
      EntryMode.confirm,
      reason:
          '${entryBloc.state.runtimeType}: ${entryBloc.state.view.draft.fields}',
    );
    await tester.drag(
      find.byKey(const ValueKey('merchant_scroll')),
      const Offset(0, 1500),
    );
    await tester.pumpAndSettle();
    final save = find.byKey(const ValueKey('entry_save'));
    await tester.ensureVisible(save);
    await tester.pumpAndSettle();
    await tester.tap(save);
    await tester.pumpAndSettle();
    expect(countSaved, isTrue);
    final scroll = tester.state<ScrollableState>(
      find
          .descendant(
            of: find.byKey(const ValueKey('merchant_scroll')),
            matching: find.byType(Scrollable),
          )
          .first,
    );
    scroll.position.jumpTo(scroll.position.maxScrollExtent);
    await tester.pumpAndSettle();
    scroll.position.jumpTo(0);
    await tester.pumpAndSettle();
    expect(find.text(l.savedSource('ENT-TEST')), findsOneWidget);
    final undo = find.text(l.undo);
    await tester.ensureVisible(undo);
    await tester.pumpAndSettle();
    expect(undo.hitTestable(), findsOneWidget);
    await tester.tap(undo);
    await tester.pumpAndSettle();
    final reason = find.byKey(const ValueKey('undo_reason'));
    await tester.ensureVisible(reason);
    await tester.pumpAndSettle();
    await tester.enterText(reason, 'mistyped');
    await tester.pumpAndSettle();
    final confirmUndo = find.text(l.confirmUndo);
    await tester.ensureVisible(confirmUndo);
    await tester.pumpAndSettle();
    await tester.tap(confirmUndo);
    await tester.pumpAndSettle();
    scroll.position.jumpTo(0);
    await tester.pumpAndSettle();
    expect(countSaved, isFalse);
    expect(find.text(l.voidSaved('VOID-TEST', 'mistyped')), findsOneWidget);
    final count = tester.widget<AmountView>(
      find.byWidgetPredicate(
        (widget) =>
            widget is AmountView && widget.hero && widget.label == l.cashCount,
      ),
    );
    expect(count.amount.value, isNull);
    expect(tester.takeException(), isNull);
  });
  testWidgets('Hidden count panel excludes keyboard focus during review', (
    tester,
  ) async {
    installRecordedApp();
    addTearDown(() => getIt.reset());
    getIt<GoRouter>().go('/close');
    await tester.pumpWidget(const ShgadApp());
    await tester.pumpAndSettle();
    final panel = find.byType(EntryPanel, skipOffstage: false);
    final hiddenInput = find
        .descendant(
          of: panel,
          matching: find.byType(EditableText, skipOffstage: false),
          skipOffstage: false,
        )
        .first;
    final focus = tester.widget<EditableText>(hiddenInput).focusNode;
    expect(focus.canRequestFocus, isFalse);
    expect(TickerMode.valuesOf(tester.element(hiddenInput)).enabled, isFalse);
    for (var tab = 0; tab < 16; tab++) {
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pump();
      expect(focus.hasFocus, isFalse);
      expect(
        FocusManager.instance.primaryFocus?.context
            ?.findAncestorWidgetOfExactType<EntryPanel>(),
        isNull,
      );
    }
    final l = AppLocalizations.of(tester.element(panel));
    final record = find.text(l.recordCloseEntries);
    await tester.ensureVisible(record);
    await tester.pumpAndSettle();
    await tester.tap(record);
    await tester.pumpAndSettle();
    expect(focus.canRequestFocus, isTrue);
    focus.requestFocus();
    await tester.pump();
    expect(focus.hasFocus, isTrue);
    expect(tester.takeException(), isNull);
  });
  testWidgets('Debt details do not transfer expansion to a different party', (
    tester,
  ) async {
    installRecordedApp();
    addTearDown(() => getIt.reset());
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    getIt<GoRouter>().go('/debts');
    await tester.pumpWidget(const ShgadApp(textScale: 1.3));
    await tester.pumpAndSettle();
    final l = AppLocalizations.of(
      tester.element(find.byType(ExpansionTile).first),
    );
    Future<void> tap(Finder target) async {
      await tester.ensureVisible(target);
      await tester.pumpAndSettle();
      await tester.tap(target);
      await tester.pumpAndSettle();
    }

    await tap(find.byType(ExpansionTile).first);
    expect(find.text('OB-CUST-01'), findsOneWidget);
    await tap(find.text(l.debtSuppliers));
    expect(find.text('OB-SUP-01'), findsNothing);
    await tap(find.byType(ExpansionTile).first);
    expect(find.text('OB-SUP-01'), findsOneWidget);
    await tap(find.text(l.debtCustomers));
    expect(find.text('OB-CUST-01'), findsNothing);
    await tap(find.byType(ExpansionTile).first);
    expect(find.text('OB-CUST-01'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('Weekly receivable labels preserve their API field context', (
    tester,
  ) async {
    final api = installRecordedApp();
    addTearDown(() => getIt.reset());
    getIt<Dio>().httpClientAdapter = WireAdapter((request) async {
      if (request.path == '/api/reports/weekly') {
        final body = weeklyJson();
        for (final field in [
          'outstanding_receivables',
          'overdue_receivables',
        ]) {
          (body[field] as Map)['label_key'] = 'total_outstanding';
        }
        return ResponseBody.fromString(
          jsonEncode(body),
          200,
          headers: {
            'content-type': ['application/json'],
          },
        );
      }
      return api.respond(request);
    });
    getIt<GoRouter>().go('/weekly');
    await tester.pumpWidget(const ShgadApp());
    await tester.pumpAndSettle();
    final l = AppLocalizations.of(tester.element(find.byType(LedgerRow).first));
    final rows = tester.widgetList<LedgerRow>(find.byType(LedgerRow));
    expect(
      rows.where((row) => row.label == l.receivables).single.amount.value,
      150000,
    );
    expect(
      rows
          .where((row) => row.label == l.overdueReceivables)
          .single
          .amount
          .value,
      30000,
    );
    expect(find.text(l.sourcedFigure), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('External labels remain names of focused editable fields', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    final controller = TextEditingController();
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      localized(
        Builder(
          builder: (context) => Column(
            children: [
              AmountField(
                fieldKey: const ValueKey('money'),
                controller: controller,
                onChanged: (_) {},
              ),
              ledgerTextField(
                context,
                key: const ValueKey('note'),
                decoration: InputDecoration(
                  labelText: AppLocalizations.of(context).noteInput,
                ),
              ),
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    final l = AppLocalizations.of(
      tester.element(find.byKey(const ValueKey('money'))),
    );
    await tester.tap(find.byKey(const ValueKey('money')));
    await tester.pump();
    final node = tester.getSemantics(find.byKey(const ValueKey('money')));
    expect(node.getSemanticsData().label, contains(l.amountInput));
    expect(node.getSemanticsData().flagsCollection.isTextField, isTrue);
    await tester.tap(find.byKey(const ValueKey('note')));
    await tester.pump();
    expect(
      tester
          .getSemantics(find.byKey(const ValueKey('note')))
          .getSemanticsData()
          .label,
      contains(l.noteInput),
    );
    semantics.dispose();
  });
  testWidgets('Choice groups expose every independent selectable control', (
    tester,
  ) async {
    final semantics = tester.ensureSemantics();
    String? chosen;
    await tester.pumpWidget(
      localized(
        FieldLabel(
          label: 'entry kind',
          group: true,
          child: ChoiceChips(
            choices: const {'cash': 'cash sale', 'credit': 'credit sale'},
            selected: 'cash',
            onSelected: (value) => chosen = value,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    for (final label in ['cash sale', 'credit sale']) {
      final node = tester.getSemantics(find.bySemanticsLabel(label));
      expect(node.getSemanticsData().hasAction(SemanticsAction.tap), isTrue);
      expect(node.getSemanticsData().rect.height, greaterThanOrEqualTo(48));
    }
    final credit = tester.getSemantics(find.bySemanticsLabel('credit sale'));
    tester.binding.performSemanticsAction(
      SemanticsActionEvent(
        type: SemanticsAction.tap,
        nodeId: credit.id,
        viewId: tester.view.viewId,
      ),
    );
    await tester.pump();
    expect(chosen, 'credit');
    semantics.dispose();
  });
  testWidgets('Today has named accessible targets at least48 pixels', (
    tester,
  ) async {
    installRecordedApp();
    addTearDown(() => getIt.reset());
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final handle = tester.ensureSemantics();
    await tester.pumpWidget(const ShgadApp(textScale: 1.3));
    await tester.pumpAndSettle();
    await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
    await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
    handle.dispose();
  });
  testWidgets('Chat Enter sends and Shift Enter retains a multiline draft', (
    tester,
  ) async {
    final controller = TextEditingController(text: 'draft');
    addTearDown(controller.dispose);
    var sent = 0;
    await tester.pumpWidget(
      localized(
        ChatComposer(
          controller: controller,
          onChanged: (_) {},
          onSubmit: () => sent++,
        ),
      ),
    );
    await tester.tap(find.byKey(const ValueKey('chat_input')));
    await tester.pump();
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump();
    expect(sent, 1);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
    await tester.pump();
    expect(sent, 1);
  });
  testWidgets('Arabic date display and picker use the server business date', (
    tester,
  ) async {
    final selectedDates = <String>[];
    await tester.pumpWidget(
      localized(
        DateField(
          label: 'date',
          value: '2026-09-28',
          businessDate: '2026-09-28',
          onChanged: selectedDates.add,
        ),
        reduced: true,
      ),
    );
    await tester.pumpAndSettle();
    final field = tester.widget<TextFormField>(find.byType(TextFormField));
    expect(field.controller!.text, '٢٠٢٦-٠٩-٢٨');
    expect(RegExp(r'[0-9]').hasMatch(field.controller!.text), isFalse);
    await tester.tap(find.byType(TextFormField));
    await tester.pump();
    final picker = tester.widget<DatePickerDialog>(
      find.byType(DatePickerDialog),
    );
    expect(picker.currentDate, DateTime(2026, 9, 28));
    expect(picker.initialDate, DateTime(2026, 9, 28));
    final material = MaterialLocalizations.of(
      tester.element(find.byType(DatePickerDialog)),
    );
    final compact = picker.calendarDelegate.formatCompactDate(
      picker.initialDate!,
      material,
    );
    final medium = picker.calendarDelegate.formatMediumDate(
      picker.initialDate!,
      material,
    );
    expect(RegExp(r'[0-9]').hasMatch(compact + medium), isFalse);
    final nativeField = tester.widget<TextFormField>(
      find.descendant(
        of: find.byType(InputDatePickerFormField),
        matching: find.byType(TextFormField),
      ),
    );
    expect(nativeField.controller!.text, compact);
    expect(
      picker.calendarDelegate.parseCompactDate(compact, material),
      DateTime(2026, 9, 28),
    );
    expect(
      picker.calendarDelegate.parseCompactDate('28/9/2026', material),
      DateTime(2026, 9, 28),
    );
    expect(picker.calendarDelegate.dateHelpText(material), isEmpty);
    final nativeInput = find.descendant(
      of: find.byType(InputDatePickerFormField),
      matching: find.byType(TextFormField),
    );
    for (final invalid in ['', '٣١/٢/٢٠٢٦']) {
      await tester.enterText(nativeInput, invalid);
      await tester.tap(find.text(material.okButtonLabel));
      await tester.pumpAndSettle();
      expect(find.byType(DatePickerDialog), findsOneWidget);
      expect(selectedDates, isEmpty);
      expect(find.text(material.invalidDateFormatLabel), findsOneWidget);
    }
    await tester.enterText(nativeInput, '٢٨/٩/٢٠٢٦');
    await tester.tap(find.text(material.okButtonLabel));
    await tester.pumpAndSettle();
    expect(selectedDates, ['2026-09-28']);
    expect(find.byType(DatePickerDialog), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('Reduced motion completes chip and expansion state immediately', (
    tester,
  ) async {
    var selected = 'first';
    await tester.pumpWidget(
      localized(
        StatefulBuilder(
          builder: (context, setState) => Column(
            children: [
              ChoiceChips(
                choices: const {'first': 'first', 'second': 'second'},
                selected: selected,
                onSelected: (v) => setState(() => selected = v),
              ),
              const ExpansionTile(
                title: Text('details'),
                children: [Text('content')],
              ),
            ],
          ),
        ),
        reduced: true,
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('second'));
    await tester.pump();
    expect(selected, 'second');
    final chip = tester.widget<ChoiceChip>(find.byType(ChoiceChip).last);
    expect(chip.chipAnimationStyle!.selectAnimation!.duration, Duration.zero);
    await tester.tap(find.text('details'));
    await tester.pump();
    expect(find.text('content').hitTestable(), findsOneWidget);
    final context = tester.element(find.byType(ExpansionTile));
    expect(
      Theme.of(context).expansionTileTheme.expansionAnimationStyle!.duration,
      Duration.zero,
    );
    expect(tester.takeException(), isNull);
  });
  for (final kind in ['hero', 'ledger']) {
    testWidgets('Real $kind amount pointer and focus states are visible', (
      tester,
    ) async {
      var taps = 0;
      const amount = Amount(
        value: 420000,
        kind: 'verified',
        label: 'cash_on_hand',
        sources: [],
        formula: '',
      );
      await tester.pumpWidget(
        localized(
          Center(
            child: RepaintBoundary(
              key: const ValueKey('amount_target'),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      width: 320,
                      child: kind == 'hero'
                          ? HeroCard(
                              amount: amount,
                              label: 'Cash on hand',
                              caption: 'Counted at the business date',
                              onTap: () => taps++,
                            )
                          : LedgerCard(
                              child: LedgerRow(
                                amount: amount,
                                label: 'Cash on hand',
                                caption: 'Counted at the business date',
                                onTap: () => taps++,
                              ),
                            ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final target = find.byKey(const ValueKey('amount_target'));
      final hit = find.byType(InkWell);
      final normal = await pixels(tester, target);
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-normal.png'),
      );
      final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
      await mouse.addPointer(location: Offset.zero);
      await mouse.moveTo(tester.getCenter(hit));
      await tester.pumpAndSettle();
      expect(await pixels(tester, target), isNot(orderedEquals(normal)));
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-hover.png'),
      );
      await mouse.down(tester.getCenter(hit));
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pump(const Duration(milliseconds: 150));
      expect(await pixels(tester, target), isNot(orderedEquals(normal)));
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-pressed.png'),
      );
      await mouse.up();
      await mouse.removePointer();
      await tester.pumpAndSettle();
      expect(taps, 1);
      FocusManager.instance.highlightStrategy =
          FocusHighlightStrategy.alwaysTraditional;
      Focus.of(tester.element(find.text('Cash on hand'))).requestFocus();
      await tester.pumpAndSettle();
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-focus.png'),
      );
      expect(
        Focus.of(tester.element(find.text('Cash on hand'))).hasPrimaryFocus,
        isTrue,
      );
      final focusedMouse = await tester.createGesture(
        kind: PointerDeviceKind.mouse,
      );
      await focusedMouse.addPointer(location: tester.getCenter(hit));
      await focusedMouse.down(tester.getCenter(hit));
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pump(const Duration(milliseconds: 150));
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-pressed-focused.png'),
      );
      await focusedMouse.up();
      await focusedMouse.removePointer();
      FocusManager.instance.highlightStrategy =
          FocusHighlightStrategy.automatic;
    });
  }
  for (final kind in ['choice', 'prompt']) {
    testWidgets('Real $kind chip pointer states have visible pixels', (
      tester,
    ) async {
      final control = kind == 'choice'
          ? ChoiceChips(
              choices: const {'a': 'First', 'b': 'Second'},
              selected: 'a',
              onSelected: (_) {},
            )
          : PromptChip(text: 'Prompt', onPressed: () {});
      await tester.pumpWidget(
        localized(
          Center(
            child: RepaintBoundary(
              key: const ValueKey('chip_target'),
              child: Padding(padding: const EdgeInsets.all(8), child: control),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final target = find.byKey(const ValueKey('chip_target'));
      final hit = find.text(kind == 'choice' ? 'First' : 'Prompt');
      final normalPixels = await pixels(tester, target);
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-normal.png'),
      );
      final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
      await mouse.addPointer(location: Offset.zero);
      await mouse.moveTo(tester.getCenter(hit));
      await tester.pumpAndSettle();
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-hover.png'),
      );
      expect(
        await pixels(tester, target),
        isNot(orderedEquals(normalPixels)),
        reason: 'Actual $kind hover must change pixels',
      );
      await mouse.down(tester.getCenter(hit));
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pump(const Duration(milliseconds: 150));
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/$kind-pressed.png'),
      );
      await mouse.up();
      await mouse.removePointer();
    });
  }
  testWidgets(
    'Real pointer hover press and keyboard focus have distinct pixels',
    (tester) async {
      await tester.pumpWidget(
        localized(
          Center(
            child: RepaintBoundary(
              key: const ValueKey('target'),
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: PrimaryButton(text: 'action', onPressed: () {}),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      final target = find.byKey(const ValueKey('target'));
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/primary-normal.png'),
      );
      final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
      await mouse.addPointer(location: Offset.zero);
      await mouse.moveTo(tester.getCenter(find.byType(FilledButton)));
      await tester.pumpAndSettle();
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/primary-hover.png'),
      );
      await mouse.down(tester.getCenter(find.byType(FilledButton)));
      await tester.pump(const Duration(milliseconds: 150));
      await tester.pump(const Duration(milliseconds: 150));
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/primary-pressed.png'),
      );
      await mouse.up();
      await mouse.moveTo(Offset.zero);
      await tester.pumpAndSettle();
      FocusManager.instance.highlightStrategy =
          FocusHighlightStrategy.alwaysTraditional;
      FocusManager.instance.primaryFocus?.unfocus();
      await tester.pump();
      addTearDown(
        () => FocusManager.instance.highlightStrategy =
            FocusHighlightStrategy.automatic,
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pumpAndSettle();
      final actionText = find.descendant(
        of: find.byType(FilledButton),
        matching: find.text('action'),
      );
      expect(Focus.of(tester.element(actionText)).hasPrimaryFocus, isTrue);
      await expectLater(
        target,
        matchesGoldenFile('goldens/interactions/primary-focus.png'),
      );
      await mouse.removePointer();
    },
  );
}
