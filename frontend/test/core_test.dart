import 'dart:async';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/cache/response_cache.dart';
import 'package:shgad/core/data/amount_model.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/network/connectivity.dart';
import 'package:shgad/core/utils/digit_normalizer.dart';
import 'package:shgad/core/utils/iqd_formatter.dart';
import 'package:shgad/core/utils/result.dart';

class MemoryCache implements ResponseCache {
  final records = <String, CacheRecord>{};
  @override
  Future<CacheRecord?> read(String key) async => records[key];
  @override
  Future<void> write(String key, CacheRecord record) async {
    records[key] = record;
  }

  @override
  Future<void> clear() async => records.clear();
}

class WireAdapter implements HttpClientAdapter {
  WireAdapter(this.respond);
  final Future<ResponseBody> Function(RequestOptions) respond;
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? request,
    Future<void>? cancel,
  ) => respond(options);
  @override
  void close({bool force = false}) {}
}

void main() {
  test(
    'Strict IQD input accepts both digit sets, rejects decimals and unsafe web integers',
    () {
      expect(DigitNormalizer.amount('١٢٣٤٥'), 12345);
      expect(DigitNormalizer.amount('۱۲۳'), 123);
      for (final text in ['-1', '0', '1.5', '1,000', '9007199254740992']) {
        expect(DigitNormalizer.amount(text), isNull);
      }
    },
  );
  test('Exact abbreviation only; evidence retains integer and signs', () {
    expect(
      IqdFormatter.format(
        9007199254740991,
        'en',
        'thousand IQD',
        'IQD',
        exact: true,
      ),
      '9,007,199,254,740,991 IQD',
    );
    expect(IqdFormatter.format(420000, 'ar', 'ألف', 'دينار'), '٤٢٠ ألف');
    expect(
      IqdFormatter.format(420001, 'en', 'thousand IQD', 'IQD'),
      '420,001 IQD',
    );
    expect(
      IqdFormatter.format(-230000, 'en', 'thousand IQD', 'IQD', exact: true),
      '-230,000 IQD',
    );
  });
  test('Missing is null; decimal amounts rejected', () {
    final value = {
      'amount_iqd': null,
      'kind': 'missing',
      'label_key': 'cash',
      'source_ids': <String>[],
      'formula': 'count',
    };
    expect(parseAmount(value).value, isNull);
    expect(
      () => parseAmount({...value, 'amount_iqd': 1.5}),
      throwsFormatException,
    );
    expect(
      () => parseAmount({...value, 'amount_iqd': 0}),
      throwsFormatException,
    );
  });
  test(
    'Web refuses unsafe IQD integers instead of displaying rounded figures',
    () {
      for (final value in [9007199254740992, -9007199254740992]) {
        expect(
          () => parseAmount({
            'amount_iqd': value,
            'kind': 'verified',
            'label_key': 'cash',
            'source_ids': ['SOURCE'],
            'formula': 'recorded',
          }),
          throwsFormatException,
        );
      }
    },
  );
  test(
    'Read cache retains server update stamp on network failure only',
    () async {
      final reader = CachedReader(MemoryCache());
      final response = {
        'last_synced_at': '2026-09-28T21:01:00+03:00',
        'counted_at': '2026-09-28T21:00:00+03:00',
      };
      await reader('today', () async => response, (j) => j);
      final result = await reader(
        'today',
        () async => throw const ApiException(AppFailure(FailureKind.offline)),
        (j) => j,
      );
      final snapshot =
          (result as Success<Snapshot<Map<String, dynamic>>>).value;
      expect(snapshot.offline, isTrue);
      expect(snapshot.updatedAt, response['last_synced_at']);
      expect(snapshot.data['counted_at'], response['counted_at']);
      expect(
        await reader(
          'today',
          () async =>
              throw const ApiException(AppFailure(FailureKind.validation)),
          (j) => j,
        ),
        isA<Failed>(),
      );
    },
  );
  test('Offline without cache is explicit; no fallback zero', () async {
    expect(
      await CachedReader(MemoryCache())(
        'today',
        () async => throw const ApiException(AppFailure(FailureKind.offline)),
        (j) => j,
      ),
      isA<Failed>(),
    );
  });
  test('API maps message keys; offline writes never enter adapter', () async {
    final connection = ConnectionSource();
    final dio = Dio();
    var calls = 0;
    dio.httpClientAdapter = WireAdapter((request) async {
      calls++;
      return ResponseBody.fromString(
        '{"error":{"code":"DIFFERENCE_SIGN_MISMATCH","message_key":"error_difference_sign_mismatch"}}',
        422,
        headers: {
          'content-type': ['application/json'],
        },
      );
    });
    final api = ApiClient(dio, connection);
    await expectLater(
      api.get('/close'),
      throwsA(
        isA<ApiException>().having(
          (e) => e.failure.messageKey,
          'key',
          'error_difference_sign_mismatch',
        ),
      ),
    );
    connection.set(false);
    await expectLater(
      api.post('/api/entries', {}),
      throwsA(isA<ApiException>()),
    );
    expect(calls, 1);
    await connection.dispose();
    dio.close();
  });
}
