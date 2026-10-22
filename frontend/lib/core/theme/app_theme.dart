import 'package:flutter/material.dart';
import '../constants/app_colors.dart';
import '../constants/app_dimens.dart';
import 'app_text_styles.dart';
import 'app_motion.dart';

abstract final class AppTheme {
  static final shape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(AppDimens.radiusMd),
  );
  static final chipShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(AppDimens.radiusSm),
  );
  static final overlay = WidgetStateProperty.resolveWith<Color?>((s) {
    if (s.contains(WidgetState.pressed)) {
      return AppColors.green.withValues(alpha: .10);
    }
    if (s.contains(WidgetState.hovered)) {
      return AppColors.green.withValues(alpha: .04);
    }
    if (s.contains(WidgetState.focused)) {
      return AppColors.green.withValues(alpha: .04);
    }
    return AppColors.transparent;
  });
  static final button = ButtonStyle(
    animationDuration: const Duration(milliseconds: 120),
    elevation: const WidgetStatePropertyAll(0),
    shape: WidgetStatePropertyAll(shape),
    overlayColor: overlay,
    backgroundColor: WidgetStateProperty.resolveWith(
      (s) => s.contains(WidgetState.disabled) ? AppColors.surfaceSunk : null,
    ),
    minimumSize: const WidgetStatePropertyAll(
      Size(AppDimens.minTarget, AppDimens.minTarget),
    ),
    padding: const WidgetStatePropertyAll(
      EdgeInsets.symmetric(horizontal: AppDimens.lg, vertical: AppDimens.md),
    ),
    textStyle: const WidgetStatePropertyAll(AppTextStyles.bodyStrong),
    foregroundColor: WidgetStateProperty.resolveWith(
      (s) => s.contains(WidgetState.disabled)
          ? AppColors.inkMuted
          : AppColors.green,
    ),
    mouseCursor: WidgetStateProperty.resolveWith(
      (s) => s.contains(WidgetState.disabled)
          ? SystemMouseCursors.basic
          : SystemMouseCursors.click,
    ),
    tapTargetSize: MaterialTapTargetSize.padded,
  );
  static OutlineInputBorder border(Color c, [double width = 1]) =>
      OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppDimens.radiusMd),
        borderSide: BorderSide(color: c, width: width),
      );
  static ThemeData get light => ThemeData(
    useMaterial3: true,
    visualDensity: VisualDensity.standard,
    materialTapTargetSize: MaterialTapTargetSize.padded,
    fontFamily: 'Cairo',
    scaffoldBackgroundColor: AppColors.paper,
    hoverColor: AppColors.green.withValues(alpha: .04),
    highlightColor: AppColors.green.withValues(alpha: .10),
    splashColor: AppColors.green.withValues(alpha: .10),
    focusColor: AppColors.green.withValues(alpha: .04),
    disabledColor: AppColors.inkMuted,
    colorScheme: const ColorScheme.light(
      primary: AppColors.green,
      onPrimary: AppColors.onGreen,
      secondary: AppColors.brassInk,
      onSecondary: AppColors.surface,
      surface: AppColors.surface,
      onSurface: AppColors.ink,
      onSurfaceVariant: AppColors.inkMuted,
      secondaryContainer: AppColors.merchantBubble,
      onSecondaryContainer: AppColors.green,
      surfaceContainerLowest: AppColors.surface,
      surfaceContainerLow: AppColors.surface,
      surfaceContainer: AppColors.surface,
      surfaceContainerHigh: AppColors.surfaceSunk,
      surfaceContainerHighest: AppColors.surfaceSunk,
      surfaceTint: AppColors.transparent,
      outline: AppColors.line,
      outlineVariant: AppColors.controlBorder,
      error: AppColors.clay,
      onError: AppColors.onGreen,
      errorContainer: AppColors.claySoft,
      onErrorContainer: AppColors.clay,
      tertiary: AppColors.greenSoft,
      onTertiary: AppColors.green,
      tertiaryContainer: AppColors.brassSoft,
      onTertiaryContainer: AppColors.brassInk,
    ),
    textTheme: const TextTheme(
      displayLarge: AppTextStyles.displayHero,
      displayMedium: AppTextStyles.displayHero,
      displaySmall: AppTextStyles.title,
      headlineLarge: AppTextStyles.displayHero,
      headlineMedium: AppTextStyles.title,
      headlineSmall: AppTextStyles.heading,
      titleLarge: AppTextStyles.title,
      titleMedium: AppTextStyles.heading,
      titleSmall: AppTextStyles.amount,
      bodyLarge: AppTextStyles.body,
      bodyMedium: AppTextStyles.body,
      bodySmall: AppTextStyles.caption,
      labelLarge: AppTextStyles.button,
      labelMedium: AppTextStyles.bodyStrong,
      labelSmall: AppTextStyles.pill,
    ),
    extensions: const [LedgerStyles()],
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.paper,
      foregroundColor: AppColors.ink,
      titleTextStyle: AppTextStyles.title,
      toolbarHeight: AppDimens.toolbarHeight,
      centerTitle: false,
      elevation: 0,
      scrolledUnderElevation: 0,
      surfaceTintColor: AppColors.transparent,
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: shape.copyWith(side: const BorderSide(color: AppColors.line)),
    ),
    dividerTheme: const DividerThemeData(
      color: AppColors.line,
      thickness: 1,
      space: 1,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: WidgetStateColor.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : AppColors.surface,
      ),
      contentPadding: const EdgeInsets.all(AppDimens.lg),
      border: border(AppColors.controlBorder),
      enabledBorder: border(AppColors.controlBorder),
      disabledBorder: border(AppColors.controlBorder),
      focusedBorder: border(AppColors.green, 2),
      errorBorder: border(AppColors.clay, 2),
      focusedErrorBorder: border(AppColors.clay, 2),
      floatingLabelBehavior: FloatingLabelBehavior.auto,
      labelStyle: AppTextStyles.bodyStrong.copyWith(color: AppColors.inkMuted),
      hintStyle: AppTextStyles.body.copyWith(color: AppColors.inkMuted),
      helperStyle: AppTextStyles.caption.copyWith(color: AppColors.inkMuted),
      errorStyle: AppTextStyles.caption.copyWith(color: AppColors.clay),
      errorMaxLines: 4,
      helperMaxLines: 4,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: button.copyWith(
        overlayColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.pressed)
              ? AppColors.onGreen.withValues(alpha: .10)
              : s.contains(WidgetState.hovered)
              ? AppColors.onGreen.withValues(alpha: .04)
              : AppColors.transparent,
        ),
        minimumSize: const WidgetStatePropertyAll(
          Size(AppDimens.minTarget, AppDimens.primaryHeight),
        ),
        textStyle: const WidgetStatePropertyAll(AppTextStyles.button),
        backgroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? AppColors.surfaceSunk
              : AppColors.green,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? AppColors.inkMuted
              : AppColors.onGreen,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: button.copyWith(
        side: const WidgetStatePropertyAll(BorderSide(color: AppColors.line)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(style: button),
    iconButtonTheme: IconButtonThemeData(
      style: button.copyWith(
        padding: const WidgetStatePropertyAll(EdgeInsets.all(AppDimens.md)),
      ),
    ),
    segmentedButtonTheme: SegmentedButtonThemeData(
      style: button.copyWith(
        padding: const WidgetStatePropertyAll(EdgeInsets.all(AppDimens.sm)),
        minimumSize: const WidgetStatePropertyAll(
          Size(0, AppDimens.segmentHeight),
        ),
        side: const WidgetStatePropertyAll(
          BorderSide(color: AppColors.controlBorder),
        ),
        backgroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? AppColors.surfaceSunk
              : s.contains(WidgetState.selected)
              ? AppColors.greenSoft
              : AppColors.surface,
        ),
        foregroundColor: WidgetStateProperty.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? AppColors.inkMuted
              : s.contains(WidgetState.selected)
              ? AppColors.green
              : s.any(
                  const {
                    WidgetState.hovered,
                    WidgetState.focused,
                    WidgetState.pressed,
                  }.contains,
                )
              ? AppColors.ink
              : AppColors.inkMuted,
        ),
      ),
    ),
    chipTheme: ChipThemeData(
      color: WidgetStateProperty.resolveWith((s) {
        final fill = s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : s.contains(WidgetState.selected)
            ? AppColors.greenSoft
            : AppColors.surface;
        // RawChip suppresses native hover ink when a colour resolver is set.
        // Press retains its native ink layer; hover must colour the surface.
        return s.contains(WidgetState.hovered) &&
                !s.contains(WidgetState.pressed) &&
                !s.contains(WidgetState.disabled)
            ? Color.alphaBlend(overlay.resolve({WidgetState.hovered})!, fill)
            : fill;
      }),
      backgroundColor: AppColors.surface,
      selectedColor: AppColors.greenSoft,
      disabledColor: AppColors.surfaceSunk,
      checkmarkColor: AppColors.green,
      labelStyle: AppTextStyles.bodyStrong.copyWith(
        color: WidgetStateColor.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? AppColors.inkMuted
              : AppColors.ink,
        ),
      ),
      secondaryLabelStyle: AppTextStyles.bodyStrong.copyWith(
        color: WidgetStateColor.resolveWith(
          (s) => s.contains(WidgetState.disabled)
              ? AppColors.inkMuted
              : AppColors.green,
        ),
      ),
      shape: chipShape,
      side: WidgetStateBorderSide.resolveWith(
        (s) => BorderSide(
          color:
              s.contains(WidgetState.selected) &&
                  !s.contains(WidgetState.disabled)
              ? AppColors.green
              : AppColors.controlBorder,
        ),
      ),
      padding: const EdgeInsets.all(AppDimens.sm),
      elevation: 0,
      pressElevation: 0,
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: AppDimens.navigationHeight,
      backgroundColor: AppColors.surface,
      surfaceTintColor: AppColors.transparent,
      elevation: 0,
      indicatorColor: AppColors.greenSoft,
      indicatorShape: chipShape,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      overlayColor: overlay,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (s) => AppTextStyles.navLabel.copyWith(
          color: s.contains(WidgetState.selected)
              ? AppColors.green
              : AppColors.inkMuted,
          fontWeight: s.contains(WidgetState.selected)
              ? FontWeight.w700
              : FontWeight.w600,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (s) => IconThemeData(
          size: AppDimens.iconSize,
          color: s.contains(WidgetState.selected)
              ? AppColors.green
              : AppColors.inkMuted,
        ),
      ),
    ),
    navigationRailTheme: NavigationRailThemeData(
      backgroundColor: AppColors.surface,
      elevation: 0,
      useIndicator: true,
      indicatorColor: AppColors.greenSoft,
      indicatorShape: chipShape,
      selectedIconTheme: const IconThemeData(
        color: AppColors.green,
        size: AppDimens.iconSize,
      ),
      unselectedIconTheme: const IconThemeData(
        color: AppColors.inkMuted,
        size: AppDimens.iconSize,
      ),
      selectedLabelTextStyle: AppTextStyles.navLabel.copyWith(
        color: AppColors.green,
        fontWeight: FontWeight.w700,
      ),
      unselectedLabelTextStyle: AppTextStyles.navLabel,
    ),
    listTileTheme: const ListTileThemeData(
      contentPadding: EdgeInsets.symmetric(
        horizontal: AppDimens.lg,
        vertical: AppDimens.xs,
      ),
      minVerticalPadding: AppDimens.md,
      titleTextStyle: AppTextStyles.bodyStrong,
      subtitleTextStyle: AppTextStyles.caption,
      iconColor: AppColors.inkMuted,
      selectedColor: AppColors.green,
      selectedTileColor: AppColors.greenSoft,
    ),
    expansionTileTheme: const ExpansionTileThemeData(
      shape: Border(),
      collapsedShape: Border(),
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      iconColor: AppColors.green,
      collapsedIconColor: AppColors.inkMuted,
    ),
    radioTheme: RadioThemeData(
      backgroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : AppColors.surface,
      ),
      overlayColor: overlay,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      fillColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.inkMuted
            : s.contains(WidgetState.selected)
            ? AppColors.green
            : AppColors.controlBorder,
      ),
    ),
    checkboxTheme: CheckboxThemeData(
      overlayColor: overlay,
      side: const BorderSide(color: AppColors.controlBorder),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppDimens.xs),
      ),
      fillColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : s.contains(WidgetState.selected)
            ? AppColors.green
            : AppColors.surface,
      ),
      checkColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.inkMuted
            : AppColors.onGreen,
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: AppColors.surface,
      elevation: 0,
      shape: shape,
      titleTextStyle: AppTextStyles.heading,
      contentTextStyle: AppTextStyles.body,
      surfaceTintColor: AppColors.transparent,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: AppColors.surface,
      elevation: 1,
      surfaceTintColor: AppColors.transparent,
      showDragHandle: true,
      dragHandleColor: AppColors.controlBorder,
      constraints: const BoxConstraints(maxWidth: AppDimens.sheetMaxWidth),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppDimens.radiusLg),
      ),
    ),
    popupMenuTheme: PopupMenuThemeData(
      color: AppColors.surface,
      elevation: 1,
      shape: shape,
      textStyle: AppTextStyles.bodyStrong,
    ),
    menuTheme: MenuThemeData(
      style: MenuStyle(
        backgroundColor: const WidgetStatePropertyAll(AppColors.surface),
        elevation: const WidgetStatePropertyAll(1),
        shape: WidgetStatePropertyAll(shape),
      ),
    ),
    menuButtonTheme: MenuButtonThemeData(style: button),
    dropdownMenuTheme: DropdownMenuThemeData(
      textStyle: AppTextStyles.body,
      menuStyle: MenuStyle(
        backgroundColor: const WidgetStatePropertyAll(AppColors.surface),
        surfaceTintColor: const WidgetStatePropertyAll(AppColors.transparent),
        elevation: const WidgetStatePropertyAll(1),
        shape: WidgetStatePropertyAll(shape),
        maximumSize: const WidgetStatePropertyAll(Size(double.infinity, 320)),
      ),
    ),
    dataTableTheme: DataTableThemeData(
      headingTextStyle: AppTextStyles.bodyStrong,
      dataTextStyle: AppTextStyles.body,
      headingRowColor: const WidgetStatePropertyAll(AppColors.surfaceSunk),
      dataRowColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.hovered)
            ? AppColors.greenSoft
            : AppColors.surface,
      ),
      horizontalMargin: AppDimens.lg,
      columnSpacing: AppDimens.xl,
      dividerThickness: 1,
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.green,
      linearTrackColor: AppColors.line,
      linearMinHeight: AppDimens.progressHeight,
    ),
    tooltipTheme: TooltipThemeData(
      textStyle: AppTextStyles.caption.copyWith(color: AppColors.ink),
      padding: const EdgeInsets.all(AppDimens.sm),
      decoration: BoxDecoration(
        color: AppColors.surfaceSunk,
        borderRadius: BorderRadius.circular(AppDimens.radiusSm),
      ),
    ),
    scrollbarTheme: const ScrollbarThemeData(
      thumbColor: WidgetStatePropertyAll(AppColors.controlBorder),
      thickness: WidgetStatePropertyAll(AppDimens.xs),
      radius: Radius.circular(AppDimens.radiusSm),
    ),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: AppColors.green,
      selectionColor: AppColors.greenSoft,
      selectionHandleColor: AppColors.green,
    ),
    datePickerTheme: DatePickerThemeData(
      backgroundColor: AppColors.surface,
      elevation: 0,
      shape: shape,
      dayShape: WidgetStatePropertyAll(chipShape),
      yearShape: WidgetStatePropertyAll(chipShape),
      dayForegroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.inkMuted
            : s.contains(WidgetState.selected)
            ? AppColors.onGreen
            : AppColors.ink,
      ),
      dayBackgroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : s.contains(WidgetState.selected)
            ? AppColors.green
            : AppColors.surface,
      ),
      dayOverlayColor: overlay,
      todayForegroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.inkMuted
            : s.contains(WidgetState.selected)
            ? AppColors.onGreen
            : AppColors.green,
      ),
      todayBackgroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : s.contains(WidgetState.selected)
            ? AppColors.green
            : AppColors.surface,
      ),
      todayBorder: const BorderSide(color: AppColors.controlBorder),
      yearForegroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.inkMuted
            : s.contains(WidgetState.selected)
            ? AppColors.onGreen
            : AppColors.ink,
      ),
      yearBackgroundColor: WidgetStateProperty.resolveWith(
        (s) => s.contains(WidgetState.disabled)
            ? AppColors.surfaceSunk
            : s.contains(WidgetState.selected)
            ? AppColors.green
            : AppColors.surface,
      ),
      yearOverlayColor: overlay,
      dayStyle: AppTextStyles.body,
      weekdayStyle: AppTextStyles.caption,
      headerHeadlineStyle: AppTextStyles.title,
    ),
    snackBarTheme: const SnackBarThemeData(
      backgroundColor: AppColors.surfaceSunk,
      contentTextStyle: AppTextStyles.body,
      actionTextColor: AppColors.green,
      elevation: 0,
    ),
  );

  static ThemeData withMotion(BuildContext context, ThemeData base) {
    final duration = AppMotion.state(context);
    ButtonStyle? timed(ButtonStyle? style) =>
        style?.copyWith(animationDuration: duration);
    return base.copyWith(
      filledButtonTheme: FilledButtonThemeData(
        style: timed(base.filledButtonTheme.style),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: timed(base.outlinedButtonTheme.style),
      ),
      textButtonTheme: TextButtonThemeData(
        style: timed(base.textButtonTheme.style),
      ),
      iconButtonTheme: IconButtonThemeData(
        style: timed(base.iconButtonTheme.style),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: timed(base.segmentedButtonTheme.style),
      ),
      menuButtonTheme: MenuButtonThemeData(
        style: timed(base.menuButtonTheme.style),
      ),
      expansionTileTheme: base.expansionTileTheme.copyWith(
        expansionAnimationStyle: AnimationStyle(
          duration: duration,
          reverseDuration: duration,
        ),
      ),
    );
  }

  /// Gallery previews resolve the same theme properties as real interactions.
  /// Pointer and keyboard regression tests additionally exercise the live controls.
  static ThemeData preview(ThemeData base, Set<WidgetState> forced) {
    ButtonStyle resolve(ButtonStyle style) => style.copyWith(
      backgroundColor: WidgetStateProperty.resolveWith((actual) {
        final states = {...actual, ...forced};
        final fill =
            style.backgroundColor?.resolve(states) ?? base.colorScheme.surface;
        final overlay =
            style.overlayColor?.resolve(states) ?? AppColors.transparent;
        return Color.alphaBlend(overlay, fill);
      }),
      foregroundColor: WidgetStateProperty.resolveWith(
        (actual) => style.foregroundColor?.resolve({...actual, ...forced}),
      ),
    );
    return base.copyWith(
      chipTheme: base.chipTheme.copyWith(
        color: WidgetStateProperty.resolveWith((actual) {
          final states = {...actual, ...forced};
          final fill = base.chipTheme.color!.resolve(states)!;
          return states.contains(WidgetState.disabled) ||
                  states.contains(WidgetState.hovered) &&
                      !states.contains(WidgetState.pressed)
              ? fill
              : Color.alphaBlend(overlay.resolve(states)!, fill);
        }),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: resolve(base.filledButtonTheme.style!),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: resolve(base.outlinedButtonTheme.style!),
      ),
      textButtonTheme: TextButtonThemeData(
        style: resolve(base.textButtonTheme.style!),
      ),
      segmentedButtonTheme: SegmentedButtonThemeData(
        style: resolve(base.segmentedButtonTheme.style!),
      ),
    );
  }
}

@immutable
class LedgerStyles extends ThemeExtension<LedgerStyles> {
  const LedgerStyles();
  TextStyle get section => AppTextStyles.label;
  TextStyle get amountSmall => AppTextStyles.amountSmall;
  TextStyle get captionOnSoft =>
      AppTextStyles.caption.copyWith(color: AppColors.inkMuted);
  TextStyle get interactiveCaption =>
      AppTextStyles.caption.copyWith(color: AppColors.ink);
  TextStyle get struckCaption =>
      AppTextStyles.caption.copyWith(decoration: TextDecoration.lineThrough);
  TextStyle get heroUnit => AppTextStyles.heading;
  Color get focus => AppColors.green;
  TextStyle input({bool enabled = true, bool amount = false}) =>
      (amount ? AppTextStyles.displayHero : AppTextStyles.body).copyWith(
        color: enabled ? AppColors.ink : AppColors.inkMuted,
      );
  @override
  LedgerStyles copyWith() => this;
  @override
  LedgerStyles lerp(covariant LedgerStyles? other, double t) => this;
}
