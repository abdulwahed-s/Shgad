import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bloc_test/bloc_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shgad/core/domain/connectivity.dart';
import 'package:shgad/core/domain/new_client_id.dart';
import 'package:shgad/core/data/amount_model.dart';
import 'package:shgad/core/domain/evidence_request.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'package:shgad/core/widgets/known_zero_evidence.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'package:shgad/features/evidence/domain/usecases/evidence_usecases.dart';
import 'package:shgad/features/evidence/presentation/bloc/evidence_bloc.dart';
import 'package:shgad/features/quick_entry/domain/usecases/entry_usecases.dart';
import 'entry_test.dart' show FakeConnection, MockEntryRepository;
import 'evidence_test.dart' show MockEvidenceRepository;

Map<String, dynamic> zeroJson() => {
  'amount_iqd': 0,
  'kind': 'calculated',
  'label_key': 'collections',
  'source_ids': <String>[],
  'formula': 'sum active recorded CREDIT_COLLECTION',
  'query_evidence': {
    'tool': 'get_sales',
    'period': {'start': '2026-09-26', 'end': '2026-09-28'},
    'filters': {
      'event_types': ['CREDIT_COLLECTION'],
      'active_only': true,
      'known_at': '2026-09-28T20:59:59+00:00',
    },
    'matching_rows': 0,
  },
};

void main() {
  late FakeConnection connection;
  late MockEvidenceRepository repository;
  blocTest<EvidenceBloc, EvidenceState>(
    'Known zero evidence loads its server proof without fetching source rows',
    build: () {
      connection = FakeConnection();
      repository = MockEvidenceRepository();
      return EvidenceBloc(
        LoadEvidence(repository),
        LoadSourceDetail(repository),
        UndoEntry(MockEntryRepository()),
        WatchConnectivity(connection),
        CheckConnectivity(connection),
        NewClientId(),
      );
    },
    act: (bloc) {
      final amount = parseAmount(zeroJson());
      bloc.add(
        OpenEvidence(
          EvidenceRequest(
            amount.sources,
            amount.formula,
            queryEvidence: amount.queryEvidence,
          ),
        ),
      );
    },
    expect: () => [
      isA<EvidenceLoading>(),
      isA<EvidenceLoaded>().having(
        (s) => s.view.request.queryEvidence!.matchingRows,
        'query rows',
        0,
      ),
    ],
    verify: (_) => verifyNever(() => repository.load(any())),
    tearDown: () => connection.controller.close(),
  );
  test('Known zero proof survives amount parsing and evidence navigation', () {
    final amount = parseAmount(zeroJson());
    final request = EvidenceRequest(
      amount.sources,
      amount.formula,
      queryEvidence: amount.queryEvidence,
    );
    expect(amount.value, 0);
    expect(request.queryEvidence!.tool, 'get_sales');
    expect(request.queryEvidence!.matchingRows, 0);
    expect(request.queryEvidence!.start, '2026-09-26');
    expect(request.queryEvidence!.originalQuery, contains('CREDIT_COLLECTION'));
    expect(request.sources, isEmpty);
  });

  test('Malformed query evidence does not turn a missing value into zero', () {
    expect(
      () => parseAmount({...zeroJson(), 'amount_iqd': null, 'kind': 'missing'}),
      throwsFormatException,
    );
    final forged = zeroJson();
    (forged['query_evidence'] as Map)['matching_rows'] = 1;
    expect(() => parseAmount(forged), throwsFormatException);
  });

  for (final locale in ['ar', 'en']) {
    testWidgets(
      'Known zero evidence displays period, empty rows and query in $locale',
      (tester) async {
        final query = parseAmount(zeroJson()).queryEvidence!;
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light,
            locale: Locale(locale),
            localizationsDelegates: AppLocalizations.localizationsDelegates,
            supportedLocales: AppLocalizations.supportedLocales,
            home: Scaffold(
              body: SingleChildScrollView(
                child: KnownZeroEvidence(query: query),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        final context = tester.element(find.byType(KnownZeroEvidence));
        final l = AppLocalizations.of(context);
        expect(find.text(l.noEvidenceRows), findsOneWidget);
        expect(
          find.textContaining(locale == 'ar' ? '٢٠٢٦' : '2026'),
          findsWidgets,
        );
        await tester.tap(find.text(l.originalFormula));
        await tester.pumpAndSettle();
        expect(find.text(query.originalQuery), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
