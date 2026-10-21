import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/cache/response_cache.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'core_test.dart' show WireAdapter, MemoryCache;
import 'support/fixtures.dart';

void main() {
  setUp(() {
    configureDependencies();
    getIt.unregister<ResponseCache>();
    getIt.registerSingleton<ResponseCache>(MemoryCache());
    getIt.unregister<Dio>();
    final dio = Dio(BaseOptions(baseUrl: 'http://fictional.test'));
    dio.httpClientAdapter = WireAdapter(
      (_) async => ResponseBody.fromString(
        jsonEncode(todayJson()),
        200,
        headers: {
          'content-type': ['application/json'],
        },
      ),
    );
    getIt.registerSingleton<Dio>(dio, dispose: (d) => d.close());
  });
  tearDown(() async => getIt.reset());
  for (final locale in [const Locale('ar'), const Locale('en')]) {
    for (final scale in [1.0, 1.3]) {
      testWidgets('${locale.languageCode} Today home 360px scale $scale', (
        tester,
      ) async {
        tester.view.physicalSize = const Size(360, 800);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(ShgadApp(locale: locale, textScale: scale));
        await tester.pumpAndSettle();
        final context = tester.element(find.byType(AmountView).first);
        final l = AppLocalizations.of(context);
        expect(find.text(l.cashOnHand), findsOneWidget);
        expect(
          Directionality.of(context),
          locale.languageCode == 'ar' ? TextDirection.rtl : TextDirection.ltr,
        );
        expect(tester.takeException(), isNull);
      });
    }
  }
}
