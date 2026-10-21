import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/cache/response_cache.dart';
import 'core_test.dart' show MemoryCache, WireAdapter;
import 'support/fixtures.dart';

void main() {
  setUp(() {
    configureDependencies();
    getIt.unregister<ResponseCache>();
    getIt.registerSingleton<ResponseCache>(MemoryCache());
    getIt.unregister<Dio>();
    final dio = Dio(BaseOptions(baseUrl: 'http://fictional.test'));
    dio.httpClientAdapter = WireAdapter(
      (request) async => ResponseBody.fromString(
        jsonEncode(
          request.path == '/api/debts'
              ? debtsJson()[request.queryParameters['direction'] == 'payable'
                    ? 'payables'
                    : 'receivables']
              : todayJson(),
        ),
        200,
        headers: {
          'content-type': ['application/json'],
        },
      ),
    );
    getIt.registerSingleton<Dio>(dio, dispose: (d) => d.close());
  });
  tearDown(() => getIt.reset());
  for (final language in ['ar', 'en']) {
    for (final scale in [1.0, 1.3]) {
      testWidgets('Debts $language long names 360px scale $scale', (
        tester,
      ) async {
        tester.view.physicalSize = const Size(360, 800);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        getIt<GoRouter>().go('/debts');
        await tester.pumpWidget(
          ShgadApp(locale: Locale(language), textScale: scale),
        );
        await tester.pumpAndSettle();
        final tile = find.byType(ExpansionTile).first;
        await tester.ensureVisible(tile);
        await tester.tap(tile);
        await tester.pumpAndSettle();
        expect(find.text('OB-CUST-01'), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    }
  }
}
