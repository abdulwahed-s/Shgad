import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'package:shgad/features/csv_import/domain/entities/csv_import.dart';
import 'package:shgad/features/csv_import/presentation/pages/csv_page.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';

void main() {
  for (final locale in ['ar', 'en']) {
    for (final table in [false, true]) {
      testWidgets(
        'CSV issue field, reason and candidates $locale table=$table',
        (tester) async {
          tester.view.physicalSize = Size(table ? 768 : 320, 1000);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          const row = CsvPreviewRow(2, null, null, null, null, [
            CsvIssue(
              2,
              'AMBIGUOUS_COUNTERPARTY',
              field: 'counterparty_id',
              candidates: [
                CsvCandidate('CUST-02', 'أبو علي - دفتر أ'),
                CsvCandidate('CUST-03', 'ابو علي - دفتر ب'),
              ],
            ),
            CsvIssue(2, 'MISSING_DUE_DATE', field: 'due_date'),
          ]);
          await tester.pumpWidget(
            MaterialApp(
              locale: Locale(locale),
              theme: AppTheme.light,
              localizationsDelegates: AppLocalizations.localizationsDelegates,
              supportedLocales: AppLocalizations.supportedLocales,
              home: Scaffold(
                body: SingleChildScrollView(
                  child: MediaQuery(
                    data: MediaQueryData(
                      size: Size(table ? 768 : 320, 1000),
                      textScaler: const TextScaler.linear(1.3),
                    ),
                    child: table
                        ? const CsvPreviewTable(rows: [row])
                        : const CsvPreviewRowView(row: row),
                  ),
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
          final l = AppLocalizations.of(tester.element(find.byType(Scaffold)));
          expect(find.textContaining(l.partyIdInput), findsOneWidget);
          expect(find.textContaining(l.csvAmbiguousParty), findsOneWidget);
          expect(find.textContaining('CUST-02'), findsOneWidget);
          expect(find.textContaining('CUST-03'), findsOneWidget);
          expect(find.textContaining(l.dueDateInput), findsOneWidget);
          expect(find.textContaining(l.errorDueDate), findsOneWidget);
          expect(tester.takeException(), isNull);
        },
      );
    }
  }
}
