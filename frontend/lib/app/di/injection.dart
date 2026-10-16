import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/dio_client.dart';
import '../router.dart';

final getIt = GetIt.instance;

void configureDependencies() {
  getIt.registerLazySingleton<Dio>(
    createDioClient,
    dispose: (client) => client.close(force: true),
  );
  getIt.registerLazySingleton<GoRouter>(
    createRouter,
    dispose: (router) => router.dispose(),
  );
}
