import '../../features/chat/data/datasources/chat_remote.dart';
import '../../features/chat/data/repositories/chat_repository_impl.dart';
import '../../features/chat/domain/repositories/chat_repository.dart';
import '../../features/chat/domain/usecases/send_chat.dart';
import '../../features/chat/presentation/bloc/chat_bloc.dart';
import '../../features/daily_close/data/datasources/close_remote.dart';
import '../../features/daily_close/data/repositories/close_repository_impl.dart';
import '../../features/daily_close/domain/repositories/close_repository.dart';
import '../../features/daily_close/domain/usecases/close_usecases.dart';
import '../../features/daily_close/presentation/bloc/close_bloc.dart';
import '../../core/domain/new_client_id.dart';
import '../../features/quick_entry/data/datasources/entry_remote.dart';
import '../../features/quick_entry/data/repositories/entry_repository_impl.dart';
import '../../features/quick_entry/domain/repositories/entry_repository.dart';
import '../../features/quick_entry/domain/usecases/entry_usecases.dart';
import '../../features/quick_entry/presentation/bloc/entry_bloc.dart';
import '../../features/debts/data/datasources/debts_remote.dart';
import '../../features/debts/data/repositories/debts_repository_impl.dart';
import '../../features/debts/domain/repositories/debts_repository.dart';
import '../../features/debts/domain/usecases/load_debts.dart';
import '../../features/debts/presentation/bloc/debts_bloc.dart';
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
  getIt.registerLazySingleton<DebtsRemote>(() => DebtsRemote(getIt()));
  getIt.registerLazySingleton<DebtsRepository>(
    () => DebtsRepositoryImpl(getIt(), getIt()),
  );
  getIt.registerLazySingleton<LoadDebts>(() => LoadDebts(getIt()));
  getIt.registerFactory<DebtsBloc>(() => DebtsBloc(getIt()));
  getIt.registerLazySingleton<NewClientId>(NewClientId.new);
  getIt.registerLazySingleton<EntryRemote>(() => EntryRemote(getIt()));
  getIt.registerLazySingleton<EntryRepository>(
    () => EntryRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<LoadEntrySetup>(() => LoadEntrySetup(getIt()));
  getIt.registerLazySingleton<SaveEntry>(() => SaveEntry(getIt()));
  getIt.registerLazySingleton<UndoEntry>(() => UndoEntry(getIt()));
  getIt.registerFactory<EntryBloc>(
    () => EntryBloc(getIt(), getIt(), getIt(), getIt(), getIt(), getIt()),
  );
  getIt.registerLazySingleton<CloseRemote>(() => CloseRemote(getIt()));
  getIt.registerLazySingleton<CloseRepository>(
    () => CloseRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<LoadClose>(() => LoadClose(getIt()));
  getIt.registerLazySingleton<ResolveClose>(() => ResolveClose(getIt()));
  getIt.registerFactory<CloseBloc>(
    () => CloseBloc(getIt(), getIt(), getIt(), getIt(), getIt(), getIt()),
  );
  getIt.registerLazySingleton<ChatRemote>(() => ChatRemote(getIt()));
  getIt.registerLazySingleton<ChatRepository>(
    () => ChatRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<SendChat>(() => SendChat(getIt()));
  getIt.registerLazySingleton<ChatBloc>(
    () => ChatBloc(getIt(), getIt(), getIt(), getIt()),
    dispose: (bloc) => bloc.close(),
  );
}
