import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/constants/app_colors.dart';
import 'package:shgad/core/theme/app_theme.dart';

double ratio(Color a, Color b) {
  final x = a.computeLuminance(), y = b.computeLuminance();
  return ((x > y ? x : y) + .05) / ((x < y ? x : y) + .05);
}

void main() {
  test('Every used ledger text/surface pair meets WCAG AA', () {
    const surfaces = [
      AppColors.paper,
      AppColors.surface,
      AppColors.surfaceSunk,
      AppColors.greenSoft,
      AppColors.merchantBubble,
      AppColors.brassSoft,
      AppColors.claySoft,
    ];
    for (final foreground in [
      AppColors.ink,
      AppColors.inkMuted,
      AppColors.green,
    ]) {
      for (final background in surfaces) {
        expect(
          ratio(foreground, background),
          greaterThanOrEqualTo(4.5),
          reason: '$foreground on $background',
        );
      }
    }
    for (final background in [AppColors.paper, AppColors.surface]) {
      expect(ratio(AppColors.inkFaint, background), greaterThanOrEqualTo(4.5));
    }
    for (final background in [
      AppColors.paper,
      AppColors.surface,
      AppColors.surfaceSunk,
      AppColors.brassSoft,
    ]) {
      expect(ratio(AppColors.brassInk, background), greaterThanOrEqualTo(4.5));
    }
    for (final background in [
      AppColors.paper,
      AppColors.surface,
      AppColors.claySoft,
    ]) {
      expect(ratio(AppColors.clay, background), greaterThanOrEqualTo(4.5));
    }
    expect(
      ratio(AppColors.onGreen, AppColors.green),
      greaterThanOrEqualTo(4.5),
    );
  });
  test('Interactive boundaries meet 3:1 on all control fills', () {
    for (final background in [
      AppColors.paper,
      AppColors.surface,
      AppColors.surfaceSunk,
      AppColors.greenSoft,
    ]) {
      expect(
        ratio(AppColors.controlBorder, background),
        greaterThanOrEqualTo(3),
      );
    }
  });
  test('Interactive captions retain AA through overlapping native ink', () {
    final foreground = AppTheme.light
        .extension<LedgerStyles>()!
        .interactiveCaption
        .color!;
    for (final surface in [AppColors.paper, AppColors.surface]) {
      var composite = surface;
      // Hover, focus, pressed highlight and pressed ripple can overlap.
      for (var layer = 0; layer < 4; layer++) {
        composite = Color.alphaBlend(
          AppTheme.overlay.resolve({
            WidgetState.hovered,
            WidgetState.focused,
            WidgetState.pressed,
          })!,
          composite,
        );
        expect(ratio(foreground, composite), greaterThanOrEqualTo(4.5));
      }
    }
  });
  test('Active segment labels retain AA through overlapping native ink', () {
    final style = AppTheme.light.segmentedButtonTheme.style!;
    for (final selected in [false, true]) {
      final states = {
        if (selected) WidgetState.selected,
        WidgetState.hovered,
        WidgetState.focused,
        WidgetState.pressed,
      };
      final foreground = style.foregroundColor!.resolve(states)!;
      var composite = style.backgroundColor!.resolve(states)!;
      for (final layer in [
        WidgetState.hovered,
        WidgetState.focused,
        WidgetState.pressed,
        WidgetState.pressed,
      ]) {
        composite = Color.alphaBlend(
          style.overlayColor!.resolve({
            if (selected) WidgetState.selected,
            layer,
          })!,
          composite,
        );
        expect(ratio(foreground, composite), greaterThanOrEqualTo(4.5));
      }
    }
  });
}
