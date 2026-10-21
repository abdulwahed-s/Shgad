import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../core/cache/response_cache.dart';
import '../../core/data/cached_reader.dart';
import '../../core/domain/connectivity.dart';
import '../../core/network/api_client.dart';
import '../../core/network/connectivity.dart';
import '../../core/network/dio_client.dart';
import '../router.dart';
import '../../features/today/data/datasources/today_remote.dart';
import '../../features/today/data/repositories/today_repository_impl.dart';
import '../../features/today/domain/repositories/today_repository.dart';
import '../../features/today/domain/usecases/load_today.dart';
import '../../features/today/presentation/bloc/today_bloc.dart';

final getIt = GetIt.instance;

void configureDependencies() {
  getIt.registerLazySingleton<ConnectionSource>(
    ConnectionSource.new,
    dispose: (source) => source.dispose(),
  );
  getIt.registerLazySingleton<Dio>(
    createDioClient,
    dispose: (client) => client.close(force: true),
  );
  getIt.registerLazySingleton<GoRouter>(
    createRouter,
    dispose: (router) => router.dispose(),
  );
  getIt.registerLazySingleton<SharedPreferencesAsync>(
    SharedPreferencesAsync.new,
  );
  getIt.registerLazySingleton<ResponseCache>(
    () => PreferencesResponseCache(getIt(), apiBaseUrl),
  );
  getIt.registerLazySingleton<CachedReader>(() => CachedReader(getIt()));
  getIt.registerLazySingleton<ApiClient>(() => ApiClient(getIt(), getIt()));
  getIt.registerLazySingleton<ConnectionRepository>(
    () => DeviceConnectionRepository(getIt(), getIt()),
  );
  getIt.registerLazySingleton<WatchConnectivity>(
    () => WatchConnectivity(getIt()),
  );
  getIt.registerLazySingleton<CheckConnectivity>(
    () => CheckConnectivity(getIt()),
  );
  getIt.registerLazySingleton<TodayRemote>(() => TodayRemote(getIt()));
  getIt.registerLazySingleton<TodayRepository>(
    () => TodayRepositoryImpl(getIt(), getIt()),
  );
  getIt.registerLazySingleton<LoadToday>(() => LoadToday(getIt()));
  getIt.registerFactory<TodayBloc>(() => TodayBloc(getIt()));
}
