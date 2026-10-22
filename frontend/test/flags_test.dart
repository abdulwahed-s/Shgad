import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/data/cached_reader.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/presentation/report_bloc.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/flags/data/datasources/flags_remote.dart';
import 'package:shgad/features/flags/data/models/flags_model.dart';
import 'package:shgad/features/flags/data/repositories/flags_repository_impl.dart';
import 'package:shgad/features/flags/domain/entities/flags.dart';
import 'package:shgad/features/flags/domain/repositories/flags_repository.dart';
import 'package:shgad/features/flags/domain/usecases/load_flags.dart';
import 'package:shgad/features/flags/presentation/bloc/flags_bloc.dart';
import 'core_test.dart' show MemoryCache;
import 'support/fixtures.dart';

class MockFlagsRemote extends Mock implements FlagsRemote {}

class MockFlagsRepository extends Mock implements FlagsRepository {}

void main() {
  test(
    'Flags repository maps real response, caches and retains timestamp offline',
    () async {
      final remote = MockFlagsRemote();
      final repo = FlagsRepositoryImpl(remote, CachedReader(MemoryCache()));
      when(remote.load).thenAnswer((_) async => flagsJson());
      final online = (await repo.load() as Success<Snapshot<Flags>>).value;
      when(
        remote.load,
      ).thenThrow(const ApiException(AppFailure(FailureKind.offline)));
      final offline = (await repo.load() as Success<Snapshot<Flags>>).value;
      expect(offline.offline, isTrue);
      expect(offline.updatedAt, online.updatedAt);
      verify(remote.load).called(2);
    },
  );
  for (final mode in ['loaded', 'offline', 'failure']) {
    blocTest<FlagsBloc, ReportState<Flags>>(
      'Flags loading to $mode',
      build: () {
        final repo = MockFlagsRepository();
        when(repo.load).thenAnswer(
          (_) async => mode == 'failure'
              ? const Failed(AppFailure(FailureKind.offline))
              : Success(
                  Snapshot(
                    FlagsModel.parse(flagsJson()),
                    'saved-stamp',
                    offline: mode == 'offline',
                  ),
                ),
        );
        return FlagsBloc(LoadFlags(repo));
      },
      act: (bloc) => bloc.add(const RefreshReport()),
      expect: () => [
        isA<ReportLoading<Flags>>(),
        switch (mode) {
          'loaded' => isA<ReportLoaded<Flags>>(),
          'offline' => isA<ReportOffline<Flags>>(),
          _ => isA<ReportFailure<Flags>>(),
        },
      ],
    );
  }
}
