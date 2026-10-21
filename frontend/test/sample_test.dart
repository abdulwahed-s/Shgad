import 'dart:async';
import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/cache/response_cache.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/session_events.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/sample_shop/data/datasources/sample_remote.dart';
import 'package:shgad/features/sample_shop/data/repositories/sample_repository_impl.dart';
import 'package:shgad/features/sample_shop/domain/entities/sample_shop.dart';
import 'package:shgad/features/sample_shop/domain/repositories/sample_repository.dart';
import 'package:shgad/features/sample_shop/domain/usecases/sample_usecases.dart';
import 'package:shgad/features/sample_shop/presentation/bloc/sample_bloc.dart';
import 'core_test.dart' show MemoryCache;
import 'entry_test.dart' show FakeConnection;

class MockSampleRemote extends Mock implements SampleRemote {}

class MockSampleRepository extends Mock implements SampleRepository {}

void main() {
  test(
    'Sample repository clears read caches and announces reset only after server success',
    () async {
      final remote = MockSampleRemote();
      final cache = MemoryCache();
      final events = SessionEvents();
      await cache.write('today', const CacheRecord({}, 'old'));
      final repo = SampleRepositoryImpl(remote, cache, events);
      when(remote.reset).thenAnswer(
        (_) async => {'ok': true, 'data_version': 'synthetic-ledger-v1'},
      );
      final signal = events.resets.first;
      expect(await repo.reset(), isA<Success<String>>());
      await signal;
      expect(await cache.read('today'), isNull);
      expect(events.generation, 1);
      await events.dispose();
    },
  );
  test(
    'Response from before sample reset cannot repopulate the new session cache',
    () async {
      final events = SessionEvents();
      final cache = MemoryCache();
      final reader = CachedReader(cache, events);
      final response = Completer<Map<String, dynamic>>();
      final pending = reader('today', () => response.future, (j) => j);
      events.reset();
      await cache.clear();
      response.complete({'old': 'data'});
      expect(await pending, isA<Failed>());
      expect(await cache.read('today'), isNull);
      await events.dispose();
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    late FakeConnection connection;
    blocTest<SampleBloc, SampleState>(
      'Sample loading to $mode',
      build: () {
        final repo = MockSampleRepository();
        connection = FakeConnection();
        when(repo.load).thenAnswer(
          (_) async => mode == 'loaded'
              ? const Success(
                  SampleShop('2026-09-28', 'synthetic-ledger-v1', true),
                )
              : Failed(
                  AppFailure(
                    mode == 'offline'
                        ? FailureKind.offline
                        : FailureKind.internal,
                  ),
                ),
        );
        return SampleBloc(
          LoadSampleShop(repo),
          ResetSampleShop(repo),
          WatchConnectivity(connection),
          CheckConnectivity(connection),
        );
      },
      act: (b) => b.add(const OpenSample()),
      expect: () => [
        isA<SampleLoading>(),
        switch (mode) {
          'loaded' => isA<SampleLoaded>(),
          'offline' => isA<SampleOffline>(),
          _ => isA<SampleFailure>(),
        },
      ],
      tearDown: () => connection.controller.close(),
    );
  }
  test('Sample reset requires confirmation and never queues offline', () async {
    final repo = MockSampleRepository();
    final connection = FakeConnection();
    when(
      repo.reset,
    ).thenAnswer((_) async => const Success('synthetic-ledger-v1'));
    final bloc = SampleBloc(
      LoadSampleShop(repo),
      ResetSampleShop(repo),
      WatchConnectivity(connection),
      CheckConnectivity(connection),
    );
    bloc.add(const ConfirmSampleReset());
    await Future<void>.delayed(Duration.zero);
    verifyNever(repo.reset);
    bloc.add(const PrepareSampleReset());
    await bloc.stream.firstWhere((s) => s.view.confirm);
    connection.set(false);
    await bloc.stream.firstWhere((s) => s is SampleOffline);
    bloc.add(const ConfirmSampleReset());
    await Future<void>.delayed(Duration.zero);
    verifyNever(repo.reset);
    connection.set(true);
    await bloc.stream.firstWhere((s) => s is SampleLoaded);
    verifyNever(repo.reset);
    bloc.add(const ConfirmSampleReset());
    await bloc.stream.firstWhere((s) => s.view.saved);
    verify(repo.reset).called(1);
    await bloc.close();
    await connection.controller.close();
  });
}
