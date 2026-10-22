import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/constants/app_colors.dart';
import 'package:shgad/core/theme/app_theme.dart';
import 'contrast_test.dart' show ratio;

void main() {
  final theme = AppTheme.light;
  const disabled = {WidgetState.disabled};
  test('Disabled Material controls use opaque, accessible colours', () {
    for (final style in [
      theme.filledButtonTheme.style!,
      theme.outlinedButtonTheme.style!,
      theme.textButtonTheme.style!,
      theme.segmentedButtonTheme.style!,
    ]) {
      expect(style.foregroundColor!.resolve(disabled), AppColors.inkMuted);
      expect(style.backgroundColor!.resolve(disabled), AppColors.surfaceSunk);
    }
    expect(
      WidgetStateProperty.resolveAs(
        theme.inputDecorationTheme.fillColor,
        disabled,
      ),
      AppColors.surfaceSunk,
    );
    expect(
      theme.extension<LedgerStyles>()!.input(enabled: false).color,
      AppColors.inkMuted,
    );
    for (final states in [
      disabled,
      {WidgetState.disabled, WidgetState.selected},
    ]) {
      expect(
        WidgetStateProperty.resolveAs(
          theme.chipTheme.labelStyle!.color,
          states,
        ),
        AppColors.inkMuted,
      );
      expect(
        WidgetStateProperty.resolveAs(
          theme.chipTheme.secondaryLabelStyle!.color,
          states,
        ),
        AppColors.inkMuted,
      );
      expect(theme.radioTheme.fillColor!.resolve(states), AppColors.inkMuted);
      expect(
        theme.checkboxTheme.fillColor!.resolve(states),
        AppColors.surfaceSunk,
      );
      expect(
        theme.checkboxTheme.checkColor!.resolve(states),
        AppColors.inkMuted,
      );
      expect(
        theme.datePickerTheme.dayForegroundColor!.resolve(states),
        AppColors.inkMuted,
      );
      expect(
        theme.datePickerTheme.yearForegroundColor!.resolve(states),
        AppColors.inkMuted,
      );
    }
  });
  test('Primary hover and pressed states change pixels and retain AA text', () {
    for (final state in [WidgetState.hovered, WidgetState.pressed]) {
      final overlay = theme.filledButtonTheme.style!.overlayColor!.resolve({
        state,
      })!;
      final composite = Color.alphaBlend(overlay, AppColors.green);
      expect(composite, isNot(AppColors.green));
      expect(ratio(AppColors.onGreen, composite), greaterThanOrEqualTo(4.5));
    }
  });
  test('Picker and error borders override inaccessible Material defaults', () {
    expect(theme.datePickerTheme.elevation, 0);
    expect(theme.dialogTheme.elevation, 0);
    expect(
      theme.datePickerTheme.yearShape!.resolve({}),
      isA<RoundedRectangleBorder>(),
    );
    expect(theme.inputDecorationTheme.errorBorder!.borderSide.width, 2);
  });
}
