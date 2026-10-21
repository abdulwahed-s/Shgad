import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/chat/presentation/pages/chat_page.dart';
import '../core/widgets/gallery_page.dart';
import '../features/today/presentation/pages/today_page.dart';
import '../features/debts/presentation/pages/debts_page.dart';
import '../features/quick_entry/presentation/pages/entry_page.dart';

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
  ],
);
