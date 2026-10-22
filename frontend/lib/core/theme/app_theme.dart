import 'package:flutter/material.dart';

import '../constants/app_colors.dart';
import 'app_text_styles.dart';

abstract final class AppTheme {
  static ThemeData get light => ThemeData(
    useMaterial3: true,
    visualDensity: VisualDensity.standard,
    fontFamily: 'Cairo',
    scaffoldBackgroundColor: AppColors.paper,
    colorScheme: const ColorScheme.light(
      primary: AppColors.green,
      onPrimary: AppColors.onGreen,
      secondary: AppColors.brass,
      onSecondary: AppColors.ink,
      surface: AppColors.surface,
      onSurface: AppColors.ink,
      onSurfaceVariant: AppColors.inkMuted,
      onSecondaryContainer: AppColors.green,
      surfaceContainerLowest: AppColors.surface,
      surfaceContainerLow: AppColors.surface,
      surfaceContainer: AppColors.surface,
      surfaceContainerHigh: AppColors.surfaceSunk,
      surfaceTint: AppColors.surface,
      surfaceContainerHighest: AppColors.surfaceSunk,
      outline: AppColors.line,
      error: AppColors.clay,
      onError: AppColors.onGreen,
      tertiary: AppColors.greenSoft,
      onTertiary: AppColors.green,
      tertiaryContainer: AppColors.brassSoft,
      onTertiaryContainer: AppColors.brass,
      errorContainer: AppColors.claySoft,
      onErrorContainer: AppColors.clay,
      secondaryContainer: AppColors.merchantBubble,
    ),
    textTheme: const TextTheme(
      titleLarge: AppTextStyles.title,
      headlineLarge: AppTextStyles.display,
      titleMedium: AppTextStyles.heading,
      titleSmall: AppTextStyles.amount,
      bodyMedium: AppTextStyles.body,
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
    popupMenuTheme: const PopupMenuThemeData(
      elevation: 0,
      color: AppColors.surface,
    ),
    dividerTheme: const DividerThemeData(color: AppColors.line, thickness: 1),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surfaceSunk,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: const BorderSide(color: AppColors.line),
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        textStyle: AppTextStyles.body.copyWith(fontWeight: FontWeight.w700),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.surface,
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(14)),
      ),
    ),
  );
}
