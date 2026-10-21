import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/new_client_id.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/network/api_client.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/features/daily_close/data/datasources/close_remote.dart';
import 'package:shgad/features/daily_close/data/models/close_model.dart';
import 'package:shgad/features/daily_close/data/repositories/close_repository_impl.dart';
import 'package:shgad/features/daily_close/domain/entities/daily_close.dart';
import 'package:shgad/features/daily_close/domain/repositories/close_repository.dart';
import 'package:shgad/features/daily_close/domain/usecases/close_usecases.dart';
import 'package:shgad/features/daily_close/presentation/bloc/close_bloc.dart';
import 'package:shgad/features/quick_entry/domain/usecases/entry_usecases.dart';
import 'entry_test.dart' show FakeConnection, MockEntryRepository;
import 'support/fixtures.dart';

class MockCloseRemote extends Mock implements CloseRemote {}

class MockCloseRepository extends Mock implements CloseRepository {}

void main() {
  setUpAll(
    () => registerFallbackValue(
      const ResolutionDraft(
        'id',
        '2026-09-28',
        'leave_unexplained',
        null,
        null,
      ),
    ),
  );
  late MockCloseRepository repo;
  late FakeConnection connection;
  CloseBloc build() => CloseBloc(
    LoadClose(repo),
    ResolveClose(repo),
    UndoEntry(MockEntryRepository()),
    WatchConnectivity(connection),
    CheckConnectivity(connection),
    NewClientId(),
  );
  setUp(() {
    repo = MockCloseRepository();
    connection = FakeConnection();
    when(
      () => repo.load(any()),
    ).thenAnswer((_) async => Success(CloseModel.parse(closeJson())));
    when(() => repo.resolve(any())).thenAnswer(
      (_) async =>
          Success(ResolutionSaved(CloseModel.parse(closeJson()), null)),
    );
  });
  tearDown(() => connection.controller.close());
  test(
    'Close repository sends null for leave unexplained and preserves typed sign errors',
    () async {
      final remote = MockCloseRemote();
      final repository = CloseRepositoryImpl(remote);
      when(() => remote.resolve(any(), any())).thenAnswer(
        (_) async => {
          'entry': null,
          'daily_close': closeJson(),
          'duplicate': false,
        },
      );
      await repository.resolve(
        const ResolutionDraft(
          'stable-id',
          '2026-09-28',
          'leave_unexplained',
          null,
          null,
        ),
      );
      final payload =
          verify(
                () => remote.resolve('2026-09-28', captureAny()),
              ).captured.single
              as Map;
      expect(payload['amount_iqd'], isNull);
      when(() => remote.resolve(any(), any())).thenThrow(
        const ApiException(
          AppFailure(
            FailureKind.validation,
            code: 'DIFFERENCE_SIGN_MISMATCH',
            messageKey: 'error_difference_sign_mismatch',
          ),
        ),
      );
      final result = await repository.resolve(
        const ResolutionDraft(
          'stable-id',
          '2026-09-28',
          'expense_unrecorded',
          25000,
          null,
        ),
      );
      expect((result as Failed).failure.code, 'DIFFERENCE_SIGN_MISMATCH');
    },
  );
  blocTest<CloseBloc, CloseState>(
    'Close loads with no preselected explanation',
    build: build,
    act: (b) => b.add(const OpenClose()),
    expect: () => [
      isA<CloseLoading>(),
      isA<CloseLoaded>().having((s) => s.view.choice, 'unselected', isNull),
    ],
  );
  blocTest<CloseBloc, CloseState>(
    'Close loading to typed failure',
    build: () {
      when(
        () => repo.load(any()),
      ).thenAnswer((_) async => const Failed(AppFailure(FailureKind.missing)));
      return build();
    },
    act: (b) => b.add(const OpenClose()),
    expect: () => [isA<CloseLoading>(), isA<CloseFailure>()],
  );
  blocTest<CloseBloc, CloseState>(
    'Close loading to offline',
    build: () {
      when(
        () => repo.load(any()),
      ).thenAnswer((_) async => const Failed(AppFailure(FailureKind.offline)));
      return build();
    },
    act: (b) => b.add(const OpenClose()),
    expect: () => [isA<CloseLoading>(), isA<CloseOffline>()],
  );
  test(
    'No resolution write until explicit choice and confirmation; leave has null amount',
    () async {
      final bloc = build();
      bloc.add(const OpenClose());
      await bloc.stream.firstWhere((s) => s is CloseLoaded);
      bloc.add(const ConfirmResolution());
      await Future<void>.delayed(Duration.zero);
      verifyNever(() => repo.resolve(any()));
      bloc.add(const ChangeResolution('choice', 'leave_unexplained'));
      await Future<void>.delayed(Duration.zero);
      bloc.add(const PrepareResolution());
      await bloc.stream.firstWhere((s) => s.view.confirm);
      bloc.add(const ConfirmResolution());
      await bloc.stream.firstWhere((s) => s.view.saved);
      final draft =
          verify(() => repo.resolve(captureAny())).captured.single
              as ResolutionDraft;
      expect(draft.amount, isNull);
      expect(bloc.state.view.choice, isNull);
      await bloc.close();
    },
  );
}
