import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/utils/result.dart';
import 'core_test.dart' show WireAdapter;
import 'support/test_app.dart';

// Freeze only the screenshot's sync label at the real fixture capture time.
// All report data still passes through the actual remote/model/cache stack.
class CapturedReader extends CachedReader {
  CapturedReader(super.cache, this.capturedAt);
  final String capturedAt;
  @override
  Future<Result<Snapshot<T>>> call<T>(
    String key,
    Future<Map<String, dynamic>> Function() request,
    T Function(Map<String, dynamic>) parse,
  ) async {
    final result = await super.call(key, request, parse);
    return switch (result) {
      Success<Snapshot<T>>(:final value) => Success(
        Snapshot(value.data, capturedAt, offline: value.offline),
      ),
      _ => result,
    };
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    await (FontLoader(
      'Cairo',
    )..addFont(rootBundle.load('assets/fonts/Cairo.ttf'))).load();
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  testWidgets('collection screen renders the actual live-drill response', (
    tester,
  ) async {
    final fixture =
        jsonDecode(
              File(
                'test/fixtures/collection_live_drill.json',
              ).readAsStringSync(),
            )
            as Map;
    expect(fixture['commit'], '196ca1ad5fce99d2bf61817c44014ccff31e4942');
    expect(fixture['kind'], 'actual_live_drill_endpoint_response');
    final recorded = installRecordedApp();
    getIt.unregister<CachedReader>();
    getIt.registerSingleton<CachedReader>(
      CapturedReader(getIt(), fixture['captured_at'] as String),
    );
    addTearDown(() => getIt.reset());
    getIt<Dio>().httpClientAdapter = WireAdapter((request) async {
      if (request.path == '/api/collections') {
        return ResponseBody.fromString(
          jsonEncode(fixture['response']),
          200,
          headers: {
            'content-type': ['application/json'],
          },
        );
      }
      return recorded.respond(request);
    });
    tester.view.physicalSize = const Size(480, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    getIt<GoRouter>().go('/collections');
    await tester.pumpWidget(
      const RepaintBoundary(key: ValueKey('live_drill'), child: ShgadApp()),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('draft_CUST-05')), findsOneWidget);
    expect(find.byKey(const ValueKey('draft_CUST-04')), findsOneWidget);
    await expectLater(
      find.byKey(const ValueKey('live_drill')),
      matchesGoldenFile('../../assets/readme/shot-collections.png'),
    );
    expect(tester.takeException(), isNull);
  });
}
