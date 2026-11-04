import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/chat/presentation/pages/chat_page.dart';
import '../core/widgets/gallery_page.dart';
import '../features/today/presentation/pages/today_page.dart';
import '../features/debts/presentation/pages/debts_page.dart';
import '../features/quick_entry/presentation/pages/entry_page.dart';
import '../features/daily_close/presentation/pages/close_page.dart';
import '../features/evidence/presentation/pages/evidence_page.dart';
import '../core/domain/evidence_request.dart';
import '../core/constants/app_dimens.dart';
import '../core/theme/app_motion.dart';
import '../features/weekly_summary/presentation/pages/weekly_page.dart';
import '../features/forecast/presentation/pages/forecast_page.dart';
import '../features/sample_shop/presentation/pages/sample_page.dart';
import '../features/csv_import/presentation/pages/csv_page.dart';
import '../features/flags/presentation/pages/flags_page.dart';
import '../features/collections/presentation/pages/collections_page.dart';

GoRouter createRouter() => GoRouter(
  routes: [
    GoRoute(
      path: '/',
      pageBuilder: (context, state) => _fade(context, state, const TodayPage()),
    ),
    GoRoute(
      path: '/chat',
      pageBuilder: (context, state) => _fade(context, state, const ChatPage()),
    ),
    GoRoute(
      path: '/debts',
      pageBuilder: (context, state) => _fade(context, state, const DebtsPage()),
    ),
    GoRoute(
      path: '/collections',
      pageBuilder: (context, state) => _fade(
        context,
        state,
        CollectionsPage(
          key: ValueKey(state.uri.toString()),
          customerId: state.uri.queryParameters['customer'],
          tone: state.uri.queryParameters['tone'] ?? 'gentle',
        ),
      ),
    ),
    GoRoute(
      path: '/entry',
      pageBuilder: (context, state) => _fade(
        context,
        state,
        EntryPage(
          key: ValueKey(state.uri.toString()),
          fields: state.uri.queryParameters,
        ),
      ),
    ),
    GoRoute(
      path: '/gallery',
      pageBuilder: (context, state) => _fade(
        context,
        state,
        GalleryPage(
          key: ValueKey(state.uri.toString()),
          initialState: state.uri.queryParameters['state'] ?? 'default',
        ),
      ),
    ),
    GoRoute(
      path: '/flags',
      pageBuilder: (context, state) => _fade(context, state, const FlagsPage()),
    ),
    GoRoute(
      path: '/import',
      pageBuilder: (context, state) => _fade(context, state, const CsvPage()),
    ),
    GoRoute(
      path: '/sample',
      pageBuilder: (context, state) =>
          _fade(context, state, const SamplePage()),
    ),
    GoRoute(
      path: '/weekly',
      pageBuilder: (context, state) =>
          _fade(context, state, const WeeklyPage()),
    ),
    GoRoute(
      path: '/forecast',
      pageBuilder: (context, state) =>
          _fade(context, state, const ForecastPage()),
    ),
    GoRoute(
      path: '/close',
      pageBuilder: (context, state) => _fade(
        context,
        state,
        ClosePage(date: state.uri.queryParameters['date']),
      ),
    ),
    GoRoute(
      path: '/evidence',
      pageBuilder: (context, state) => EvidenceModalPage(
        key: state.pageKey,
        request: state.extra is EvidenceRequest
            ? state.extra as EvidenceRequest
            : EvidenceRequest(
                state.uri.queryParameters['ids']?.split(',') ?? [],
                state.uri.queryParameters['formula'] ?? '',
              ),
      ),
    ),
  ],
);

class EvidenceModalPage extends Page<void> {
  const EvidenceModalPage({required this.request, super.key});
  final EvidenceRequest request;
  @override
  Route<void> createRoute(BuildContext context) => ModalBottomSheetRoute<void>(
    settings: this,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: false,
    sheetAnimationStyle: const AnimationStyle(
      duration: Duration.zero,
      reverseDuration: Duration.zero,
    ),
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(
        top: Radius.circular(AppDimens.radiusLg),
      ),
    ),
    elevation: 1,
    builder: (_) => SoftEntrance(
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: .92,
        minChildSize: .45,
        maxChildSize: .96,
        builder: (_, controller) =>
            EvidencePage(request: request, controller: controller),
      ),
    ),
  );
}

Page<void> _fade(BuildContext context, GoRouterState state, Widget child) =>
    CustomTransitionPage<void>(
      key: state.pageKey,
      child: child,
      transitionDuration: AppMotion.route(context),
      reverseTransitionDuration: AppMotion.route(context),
      transitionsBuilder: (context, animation, secondary, child) =>
          FadeTransition(opacity: animation, child: child),
    );
