import 'package:dio/dio.dart';
import '../error/app_failure.dart';
import 'connectivity.dart';

class ApiException implements Exception {
  const ApiException(this.failure);
  final AppFailure failure;
}

class ApiClient {
  ApiClient(this.dio, this.connection);
  final Dio dio;
  final ConnectionSource connection;
  Future<Map<String, dynamic>> get(
    String path, [
    Map<String, dynamic>? query,
  ]) => _request(() => dio.get<Object>(path, queryParameters: query));
  Future<Map<String, dynamic>> post(String path, [Object? data]) async {
    if (!connection.online) {
      throw const ApiException(AppFailure(FailureKind.offline));
    }
    return _request(() => dio.post<Object>(path, data: data));
  }

  Future<Map<String, dynamic>> _request(
    Future<Response<Object>> Function() request,
  ) async {
    try {
      final response = await request();
      connection.set(true);
      return Map<String, dynamic>.from(response.data as Map);
    } on DioException catch (e) {
      if (e.response == null) {
        connection.set(false);
        throw const ApiException(AppFailure(FailureKind.offline));
      }
      connection.set(true);
      final data = e.response?.data;
      final error = data is Map ? data['error'] : null;
      final code = error is Map ? error['code'] as String? ?? '' : '';
      final key = error is Map ? error['message_key'] as String? ?? '' : '';
      final kind = switch (code) {
        'NOT_FOUND' => FailureKind.notFound,
        'LLM_UNAVAILABLE' || 'LLM_RATE_LIMITED' => FailureKind.unavailable,
        'MISSING_OPENING_BALANCE' ||
        'MISSING_COSTS' ||
        'MISSING_COUNT' ||
        'MISSING_FORECAST_HISTORY' ||
        'MISSING_DUE_DATE' => FailureKind.missing,
        'INTERNAL' => FailureKind.internal,
        _ => FailureKind.validation,
      };
      throw ApiException(AppFailure(kind, code: code, messageKey: key));
    } on ApiException {
      rethrow;
    } catch (_) {
      throw const ApiException(AppFailure(FailureKind.internal));
    }
  }
}
