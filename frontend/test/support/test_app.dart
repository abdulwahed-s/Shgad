import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/cache/response_cache.dart';
import 'package:shgad/core/domain/picked_file.dart';
import 'package:shgad/features/csv_import/data/datasources/csv_picker.dart';
import '../core_test.dart' show MemoryCache, WireAdapter;
import 'fixtures.dart';
import 'collection_fixtures.dart';

class RecordedCsvPicker implements CsvPicker {
  @override
  Future<PickedFile?> pick() async => PickedFile(
    'fictional.csv',
    Uint8List.fromList(
      utf8.encode(
        'Ref,At,Kind,IQD\nCSV-1,2026-09-28T10:00:00+03:00,CASH_SALE,12000\n',
      ),
    ),
  );
}

class RecordedApi {
  bool offline = false;
  final requests = <RequestOptions>[];
  Future<ResponseBody> respond(RequestOptions request) async {
    if (offline) {
      throw DioException(
        requestOptions: request,
        type: DioExceptionType.connectionError,
      );
    }
    requests.add(request);
    final path = request.path;
    final Object body;
    if (path == '/api/brief') {
      body = morningBriefJson();
    } else if (path == '/health') {
      body = {'status': 'ok', 'version': '0.1.0'};
    } else if (path == '/api/meta') {
      body = {
        'business_as_of': '2026-09-28',
        'week_start': 'saturday',
        'data_version': 'synthetic-ledger-v1',
        'llm_available': true,
        'merchant': {'id': 'DEMO-01', 'display_name_key': 'demo_shop_name'},
      };
    } else if (path == '/api/obligations/upcoming') {
      body = todayJson();
    } else if (path == '/api/debts') {
      body =
          debtsJson()[request.queryParameters['direction'] == 'payable'
                  ? 'payables'
                  : 'receivables']
              as Map;
    } else if (path == '/api/reports/weekly') {
      body = weeklyJson();
    } else if (path == '/api/reports/forecast') {
      body = forecastJson();
    } else if (path == '/api/flags') {
      body = flagsJson();
    } else if (path.startsWith('/api/daily-close/')) {
      body = path.endsWith('/resolve')
          ? {'entry': null, 'daily_close': closeJson(), 'duplicate': false}
          : closeJson();
    } else if (path == '/api/chat') {
      body = chatJson();
    } else if (path == '/api/evidence/sources') {
      final ids = (request.queryParameters['ids'] as String).split(',');
      body = {
        'items': [
          for (final id in ids)
            id == 'CAT-01'
                ? {
                    'kind': 'category',
                    'source_id': id,
                    'transaction': null,
                    'opening_balance': null,
                    'category': {
                      'category_id': id,
                      'name': 'سلعة تجريبية',
                      'buy_price_iqd': 1000,
                      'sell_price_iqd': 5000,
                    },
                  }
                : {
                    'kind': 'transaction',
                    'source_id': id,
                    'transaction':
                        ledgerJson(id: id, voided: id == 'ENT-ORIGINAL')
                          ..addAll(
                            id == 'CNT-090'
                                ? {
                                    'type': 'DAILY_CASH_COUNT',
                                    'amount_iqd': 420000,
                                  }
                                : {},
                          ),
                    'opening_balance': null,
                    'category': null,
                  },
        ],
      };
    } else if (path.startsWith('/api/ledger/transactions/')) {
      body = ledgerJson(
        id: path.split('/').last,
        voided: path.endsWith('ENT-ORIGINAL'),
      );
    } else if (path == '/api/imports/csv/mapping') {
      body = csvPreviewJson();
    } else if (path.endsWith('/confirm') && path.startsWith('/api/imports')) {
      body = csvReceiptJson();
    } else if (path == '/api/demo/reset') {
      body = {'ok': true, 'data_version': 'synthetic-ledger-v1'};
    } else if (path == '/api/entries') {
      body = {
        'source_id': 'ENT-TEST',
        'transaction_id': 'TX-TEST',
        'duplicate': false,
      };
    } else if (path.startsWith('/api/entries/') && path.endsWith('/void')) {
      body = {
        'source_id': path.split('/')[3],
        'status': 'voided',
        'void_id': 'VOID-TEST',
        'reason': 'mistyped',
        'duplicate': false,
      };
    } else {
      throw StateError('Unexpected synthetic test API path: $path');
    }
    return ResponseBody.fromString(
      jsonEncode(body),
      200,
      headers: {
        'content-type': ['application/json'],
      },
    );
  }
}

RecordedApi installRecordedApp() {
  configureDependencies();
  getIt.unregister<ResponseCache>();
  getIt.registerSingleton<ResponseCache>(MemoryCache());
  getIt.unregister<CsvPicker>();
  getIt.registerSingleton<CsvPicker>(RecordedCsvPicker());
  getIt.unregister<Dio>();
  final api = RecordedApi();
  final dio = Dio(BaseOptions(baseUrl: 'http://fictional.test'));
  dio.httpClientAdapter = WireAdapter(api.respond);
  getIt.registerSingleton<Dio>(dio, dispose: (d) => d.close());
  return api;
}
