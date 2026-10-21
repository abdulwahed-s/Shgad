import '../../core/domain/session_events.dart';
import '../../features/sample_shop/data/datasources/sample_remote.dart';
import '../../features/sample_shop/data/repositories/sample_repository_impl.dart';
import '../../features/sample_shop/domain/repositories/sample_repository.dart';
import '../../features/sample_shop/domain/usecases/sample_usecases.dart';
import '../../features/sample_shop/presentation/bloc/sample_bloc.dart';
import '../../features/forecast/data/datasources/forecast_remote.dart';
import '../../features/forecast/data/repositories/forecast_repository_impl.dart';
import '../../features/forecast/domain/repositories/forecast_repository.dart';
import '../../features/forecast/domain/usecases/load_forecast.dart';
import '../../features/forecast/presentation/bloc/forecast_bloc.dart';
import '../../features/weekly_summary/data/datasources/weekly_summary_remote.dart';
import '../../features/weekly_summary/data/repositories/weekly_summary_repository_impl.dart';
import '../../features/weekly_summary/domain/repositories/weekly_summary_repository.dart';
import '../../features/weekly_summary/domain/usecases/load_weekly_summary.dart';
import '../../features/weekly_summary/presentation/bloc/weekly_summary_bloc.dart';
import '../../features/evidence/data/datasources/evidence_remote.dart';
import '../../features/evidence/data/repositories/evidence_repository_impl.dart';
import '../../features/evidence/domain/repositories/evidence_repository.dart';
import '../../features/evidence/domain/usecases/evidence_usecases.dart';
import '../../features/evidence/presentation/bloc/evidence_bloc.dart';
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
  getIt.registerLazySingleton<CachedReader>(
    () => CachedReader(getIt(), getIt()),
  );
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
  getIt.registerFactory<TodayBloc>(() => TodayBloc(getIt(), getIt()));
  getIt.registerLazySingleton<DebtsRemote>(() => DebtsRemote(getIt()));
  getIt.registerLazySingleton<DebtsRepository>(
    () => DebtsRepositoryImpl(getIt(), getIt()),
  );
  getIt.registerLazySingleton<LoadDebts>(() => LoadDebts(getIt()));
  getIt.registerFactory<DebtsBloc>(() => DebtsBloc(getIt(), getIt()));
  getIt.registerLazySingleton<NewClientId>(NewClientId.new);
  getIt.registerLazySingleton<EntryRemote>(() => EntryRemote(getIt()));
  getIt.registerLazySingleton<EntryRepository>(
    () => EntryRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<LoadEntrySetup>(() => LoadEntrySetup(getIt()));
  getIt.registerLazySingleton<SaveEntry>(() => SaveEntry(getIt()));
  getIt.registerLazySingleton<UndoEntry>(() => UndoEntry(getIt()));
  getIt.registerFactory<EntryBloc>(
    () => EntryBloc(
      getIt(),
      getIt(),
      getIt(),
      getIt(),
      getIt(),
      getIt(),
      getIt(),
    ),
  );
  getIt.registerLazySingleton<CloseRemote>(() => CloseRemote(getIt()));
  getIt.registerLazySingleton<CloseRepository>(
    () => CloseRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<LoadClose>(() => LoadClose(getIt()));
  getIt.registerLazySingleton<ResolveClose>(() => ResolveClose(getIt()));
  getIt.registerFactory<CloseBloc>(
    () => CloseBloc(
      getIt(),
      getIt(),
      getIt(),
      getIt(),
      getIt(),
      getIt(),
      getIt(),
    ),
  );
  getIt.registerLazySingleton<ChatRemote>(() => ChatRemote(getIt()));
  getIt.registerLazySingleton<ChatRepository>(
    () => ChatRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<SendChat>(() => SendChat(getIt()));
  getIt.registerLazySingleton<ChatBloc>(
    () => ChatBloc(getIt(), getIt(), getIt(), getIt(), getIt()),
    dispose: (bloc) => bloc.close(),
  );
  getIt.registerLazySingleton<EvidenceRemote>(() => EvidenceRemote(getIt()));
  getIt.registerLazySingleton<EvidenceRepository>(
    () => EvidenceRepositoryImpl(getIt()),
  );
  getIt.registerLazySingleton<LoadEvidence>(() => LoadEvidence(getIt()));
  getIt.registerLazySingleton<LoadSourceDetail>(
    () => LoadSourceDetail(getIt()),
  );
  getIt.registerFactory<EvidenceBloc>(
    () => EvidenceBloc(getIt(), getIt(), getIt(), getIt(), getIt(), getIt()),
  );
  getIt.registerLazySingleton<WeeklySummaryRemote>(
    () => WeeklySummaryRemote(getIt()),
  );
  getIt.registerLazySingleton<WeeklySummaryRepository>(
    () => WeeklySummaryRepositoryImpl(getIt(), getIt()),
  );
  getIt.registerLazySingleton<LoadWeeklySummary>(
    () => LoadWeeklySummary(getIt()),
  );
  getIt.registerFactory<WeeklySummaryBloc>(
    () => WeeklySummaryBloc(getIt(), getIt()),
  );
  getIt.registerLazySingleton<ForecastRemote>(() => ForecastRemote(getIt()));
  getIt.registerLazySingleton<ForecastRepository>(
    () => ForecastRepositoryImpl(getIt(), getIt()),
  );
  getIt.registerLazySingleton<LoadForecast>(() => LoadForecast(getIt()));
  getIt.registerFactory<ForecastBloc>(() => ForecastBloc(getIt(), getIt()));
  getIt.registerLazySingleton<SessionEvents>(
    SessionEvents.new,
    dispose: (events) => events.dispose(),
  );
  getIt.registerLazySingleton<WatchSessionReset>(
    () => WatchSessionReset(getIt()),
  );
  getIt.registerLazySingleton<SampleRemote>(() => SampleRemote(getIt()));
  getIt.registerLazySingleton<SampleRepository>(
    () => SampleRepositoryImpl(getIt(), getIt(), getIt()),
  );
  getIt.registerLazySingleton<LoadSampleShop>(() => LoadSampleShop(getIt()));
  getIt.registerLazySingleton<ResetSampleShop>(() => ResetSampleShop(getIt()));
  getIt.registerFactory<SampleBloc>(
    () => SampleBloc(getIt(), getIt(), getIt(), getIt()),
  );
}
