import 'package:flutter/material.dart';

import 'app/app.dart';
import 'app/di/injection.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  configureDependencies();
  final options = Uri.base.queryParameters;
  runApp(
    ShgadApp(
      locale: Locale(options['lang'] == 'en' ? 'en' : 'ar'),
      textScale: double.tryParse(options['scale'] ?? ''),
    ),
  );
}
