import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/cache/response_cache.dart';
import 'package:shgad/core/network/connectivity.dart';
import 'package:shgad/core/utils/date_formatter.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'core_test.dart' show MemoryCache, WireAdapter;
import 'support/fixtures.dart';

void main() {
  late bool offline;
  late int writes;
  setUp(() {
    offline = false;
    writes = 0;
    configureDependencies();
    getIt.unregister<ResponseCache>();
    getIt.registerSingleton<ResponseCache>(MemoryCache());
    getIt.unregister<Dio>();
    final dio = Dio(BaseOptions(baseUrl: 'http://fictional.test'));
    dio.httpClientAdapter = WireAdapter((request) async {
      if (offline) {
        throw DioException(
          requestOptions: request,
          type: DioExceptionType.connectionError,
        );
      }
      final body = switch (request.path) {
        '/api/meta' => {'business_as_of': '2026-09-28'},
        '/api/debts' =>
          debtsJson()[request.queryParameters['direction'] == 'payable'
              ? 'payables'
              : 'receivables'],
        '/api/entries' => {
          'source_id': 'ENT-TEST',
          'transaction_id': 'TX-TEST',
          'duplicate': false,
        },
        '/api/entries/ENT-TEST/void' => {
          'source_id': 'ENT-TEST',
          'status': 'voided',
          'void_id': 'VOID-TEST',
          'reason': 'mistyped',
          'duplicate': false,
        },
        _ => todayJson(),
      };
      if (request.method == 'POST') writes++;
      return ResponseBody.fromString(
        jsonEncode(body),
        200,
        headers: {
          'content-type': ['application/json'],
        },
      );
    });
    getIt.registerSingleton<Dio>(dio, dispose: (d) => d.close());
  });
  tearDown(() => getIt.reset());
  testWidgets(
    'T33 cached Today preserves count/update; entry disables save and retains typed values',
    (tester) async {
      await tester.pumpWidget(const ShgadApp());
      await tester.pumpAndSettle();
      final router = getIt<GoRouter>();
      router.push('/entry');
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('amount_iqd')), '١٢٠٠٠');
      await tester.enterText(
        find.byKey(const ValueKey('note')),
        'ملاحظة محفوظة',
      );
      await tester.pump();
      offline = true;
      getIt<ConnectionSource>().set(false);
      await tester.pumpAndSettle();
      final review = tester.widget<PrimaryButton>(
        find.byKey(const ValueKey('entry_review')),
      );
      expect(review.onPressed, isNull);
      expect(
        tester
            .widget<TextFormField>(find.byKey(const ValueKey('amount_iqd')))
            .controller!
            .text,
        '١٢٠٠٠',
      );
      expect(find.text('ملاحظة محفوظة'), findsOneWidget);
      expect(writes, 0);
      router.go('/');
      await tester.pumpAndSettle();
      expect(find.byType(OfflineBanner), findsOneWidget);
      final l = AppLocalizations.of(tester.element(find.byType(OfflineBanner)));
      expect(
        find.text(
          l.countedAt(
            l.timeInBaghdad(
              formatDate(
                todayJson()['counted_at'] as String,
                l.localeName,
                timestamp: true,
              ),
            ),
          ),
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          l.offlineUpdated(
            l.timeInBaghdad(
              formatDate(
                todayJson()['last_synced_at'] as String,
                l.localeName,
                timestamp: true,
              ),
            ),
          ),
        ),
        findsOneWidget,
      );
      expect(writes, 0);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'Entry confirms before write and displays source ID plus reasoned undo',
    (tester) async {
      getIt<GoRouter>().go('/entry');
      await tester.pumpWidget(const ShgadApp(locale: Locale('en')));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('amount_iqd')), '12000');
      await tester.ensureVisible(find.byKey(const ValueKey('entry_review')));
      await tester.tap(find.byKey(const ValueKey('entry_review')));
      await tester.pumpAndSettle();
      expect(writes, 0);
      expect(
        find.text('Save Recorded cash sale on 2026/09/28?'),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const ValueKey('entry_save')));
      await tester.pumpAndSettle();
      expect(find.text('Saved · source ENT-TEST'), findsOneWidget);
      expect(writes, 1);
      await tester.tap(find.text('Undo entry'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('undo_reason')),
        'mistyped',
      );
      await tester.ensureVisible(find.text('Confirm undo'));
      await tester.tap(find.text('Confirm undo'));
      await tester.pumpAndSettle();
      expect(find.text('Void VOID-TEST · mistyped'), findsOneWidget);
      expect(writes, 2);
    },
  );
}
