import 'package:dio/dio.dart';

const apiBaseUrl = String.fromEnvironment('API_BASE_URL');

Dio createDioClient() {
  final uri = Uri.tryParse(apiBaseUrl);
  if (uri == null ||
      !uri.hasAuthority ||
      (uri.scheme != 'http' && uri.scheme != 'https')) {
    throw StateError(
      'Set API_BASE_URL to the Shgad backend with --dart-define.',
    );
  }
  return Dio(
    BaseOptions(
      baseUrl: apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 15),
    ),
  );
}
