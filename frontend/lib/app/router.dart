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

GoRouter createRouter() => GoRouter(
  routes: [
    GoRoute(path: '/', builder: (context, state) => const TodayPage()),
    GoRoute(path: '/chat', builder: (context, state) => const ChatPage()),
    GoRoute(path: '/debts', builder: (context, state) => const DebtsPage()),
    GoRoute(
      path: '/entry',
      builder: (context, state) => EntryPage(
        key: ValueKey(state.uri.toString()),
        fields: state.uri.queryParameters,
      ),
    ),
    GoRoute(path: '/gallery', builder: (context, state) => const GalleryPage()),
    GoRoute(
      path: '/close',
      builder: (context, state) =>
          ClosePage(date: state.uri.queryParameters['date']),
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
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(
        top: Radius.circular(AppDimens.radiusLg),
      ),
    ),
    elevation: 1,
    builder: (_) => FractionallySizedBox(
      heightFactor: .92,
      child: EvidencePage(request: request),
    ),
  );
}
