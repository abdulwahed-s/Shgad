import 'package:go_router/go_router.dart';

import '../features/chat/presentation/pages/chat_page.dart';

GoRouter createRouter() => GoRouter(
  routes: [GoRoute(path: '/', builder: (context, state) => const ChatPage())],
);
