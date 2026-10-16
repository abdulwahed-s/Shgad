import 'package:flutter/material.dart';

import '../constants/app_colors.dart';
import 'app_text_styles.dart';

abstract final class AppTheme {
  static ThemeData get light => ThemeData(
    useMaterial3: true,
    fontFamily: 'Cairo',
    scaffoldBackgroundColor: AppColors.paper,
    colorScheme: const ColorScheme.light(
      primary: AppColors.green,
      onPrimary: AppColors.onGreen,
      secondary: AppColors.brass,
      onSecondary: AppColors.ink,
      surface: AppColors.surface,
      onSurface: AppColors.ink,
      surfaceContainerHighest: AppColors.surfaceSunk,
      outline: AppColors.line,
      error: AppColors.clay,
      onError: AppColors.onGreen,
    ),
    textTheme: const TextTheme(
      titleLarge: AppTextStyles.title,
      bodyLarge: AppTextStyles.body,
      labelLarge: AppTextStyles.label,
      bodySmall: AppTextStyles.caption,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.paper,
      foregroundColor: AppColors.ink,
      titleTextStyle: AppTextStyles.title,
      centerTitle: false,
      elevation: 0,
      scrolledUnderElevation: 0,
    ),
    dividerTheme: const DividerThemeData(color: AppColors.line, thickness: 1),
  );
}
