import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:shgad/app/app.dart';
import 'package:shgad/app/di/injection.dart';
import 'package:shgad/core/domain/snapshot.dart';
import 'package:shgad/core/error/app_failure.dart';
import 'package:shgad/core/utils/result.dart';
import 'package:shgad/core/widgets/failure_view.dart';
import 'package:shgad/features/collections/data/models/collections_model.dart';
import 'package:shgad/features/collections/domain/entities/collections.dart';
import 'package:shgad/features/collections/domain/repositories/collections_repository.dart';
import 'package:shgad/features/collections/presentation/pages/collections_page.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';
import 'collections_bloc_test.dart' show FakeCollectionsRepository, FakeSharing;
import 'collections_model_test.dart' show collectionsJson;
import 'support/test_app.dart';

class WidgetCollections extends FakeCollectionsRepository {
  bool empty = false, failed = false;
  int loads = 0;
  @override
  Future<Result<Snapshot<Collections>>> load() async {
    loads++;
    return failed
        ? const Failed(AppFailure(FailureKind.unavailable))
        : Success(
            Snapshot(
              CollectionsModel.collections({
                ...collectionsJson(),
                if (empty) 'items': <Object>[],
              }),
              '2026-11-04T10:00:00Z',
            ),
          );
  }
}

void main() {
  late WidgetCollections repo;
  late FakeSharing sharing;
  setUp(() {
    installRecordedApp();
    repo = WidgetCollections();
    sharing = FakeSharing();
    getIt.unregister<CollectionsRepository>();
    getIt.registerSingleton<CollectionsRepository>(repo);
    getIt.unregister<ReminderSharingRepository>();
    getIt.registerSingleton<ReminderSharingRepository>(sharing);
  });
  tearDown(() => getIt.reset());
  Future<void> open(
    WidgetTester tester, {
    String locale = 'ar',
    double width = 360,
    double scale = 1,
    String location = '/collections',
  }) async {
    tester.view.physicalSize = Size(width, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    getIt<GoRouter>().go(location);
    await tester.pumpWidget(ShgadApp(locale: Locale(locale), textScale: scale));
    await tester.pumpAndSettle();
  }

  Future<void> tap(WidgetTester tester, Finder finder) async {
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  for (final locale in ['ar', 'en']) {
    testWidgets('collection list and draft sheet $locale at 320px 1.3', (
      tester,
    ) async {
      await open(tester, locale: locale, width: 320, scale: 1.3);
      expect(find.byType(CollectionsPage), findsOneWidget);
      expect(find.text('أم نور'), findsWidgets);
      await tap(tester, find.byKey(const ValueKey('draft_CUST-01')));
      expect(
        find.byKey(const ValueKey('collection_draft_text')),
        findsOneWidget,
      );
      final l = AppLocalizations.of(
        tester.element(find.byKey(const ValueKey('collection_draft_text'))),
      );
      expect(find.text(l.collectionGentle), findsOneWidget);
      expect(find.text(l.collectionFirm), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
  for (final channel in ['copy', 'whatsapp']) {
    testWidgets('$channel action logs only after user tap', (tester) async {
      await open(tester);
      await tap(tester, find.byKey(const ValueKey('draft_CUST-01')));
      expect(repo.actions, isEmpty);
      expect(sharing.texts, isEmpty);
      await tester.enterText(
        find.byKey(const ValueKey('collection_draft_text')),
        'edited by merchant',
      );
      await tester.pumpAndSettle();
      await tap(tester, find.byKey(ValueKey('collection_$channel')));
      expect(sharing.texts, ['edited by merchant']);
      expect(repo.actions.single.channel, channel);
      expect(find.byKey(const ValueKey('reminder_confirmed')), findsOneWidget);
      final l = AppLocalizations.of(
        tester.element(find.byKey(const ValueKey('reminder_confirmed'))),
      );
      expect(
        find.text(
          channel == 'copy'
              ? l.collectionCopiedLogged
              : l.collectionHandoffLogged,
        ),
        findsOneWidget,
      );
    });
  }
  testWidgets('empty collection state', (tester) async {
    repo.empty = true;
    await open(tester);
    expect(find.byKey(const ValueKey('collections_empty')), findsOneWidget);
  });
  testWidgets('error collection state', (tester) async {
    repo.failed = true;
    await open(tester);
    expect(find.byType(FailureView), findsOneWidget);
  });
  testWidgets('chat deep link refreshes reminder memory on sheet close', (
    tester,
  ) async {
    await open(tester, location: '/collections?customer=CUST-01&tone=firm');
    expect(find.byKey(const ValueKey('collection_draft_text')), findsOneWidget);
    expect(repo.loads, 1);
    Navigator.of(
      tester.element(find.byKey(const ValueKey('collection_draft_text'))),
    ).pop();
    await tester.pumpAndSettle();
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('collection_draft_text')), findsNothing);
    expect(find.byType(CollectionsPage), findsOneWidget);
    expect(repo.loads, 2);
  });
}
