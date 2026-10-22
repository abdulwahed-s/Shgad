import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/widgets/gallery_page.dart';
import 'package:shgad/core/widgets/ledger_widgets.dart';
import 'components_layout_test.dart' show host;

void main() {
  for (final width in [360.0, 1280.0]) {
    for (final state in [
      'default',
      'hover',
      'focus',
      'pressed',
      'disabled',
      'loading',
      'error',
      'offline',
    ]) {
      testWidgets(
        'Gallery $state at$width has real control state and no overflow',
        (tester) async {
          tester.view.physicalSize = Size(width, 800);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          await tester.pumpWidget(
            host(GalleryPage(initialState: state), width: width),
          );
          await tester.pump(const Duration(milliseconds: 220));
          final button = tester.widget<PrimaryButton>(
            find.byType(PrimaryButton).first,
          );
          if (state == 'disabled') {
            expect(button.onPressed, isNull);
            for (final id in [
              'actions',
              'text_action',
              'empty',
              'composer',
              'meta',
              'evidence',
            ]) {
              final specimen = find.byKey(ValueKey('gallery_$id'));
              await tester.scrollUntilVisible(
                specimen,
                300,
                scrollable: find.byType(Scrollable).first,
              );
              await tester.pump(const Duration(milliseconds: 220));
              for (final widget in tester.widgetList(
                find.descendant(
                  of: specimen,
                  matching: find.byWidgetPredicate(
                    (w) =>
                        w is PrimaryButton ||
                        w is SecondaryButton ||
                        w is TextAction ||
                        w is IconButton,
                  ),
                ),
              )) {
                final callback = switch (widget) {
                  PrimaryButton(:final onPressed) => onPressed,
                  SecondaryButton(:final onPressed) => onPressed,
                  TextAction(:final onPressed) => onPressed,
                  IconButton(:final onPressed) => onPressed,
                  _ => throw StateError('Unexpected control'),
                };
                expect(
                  callback,
                  isNull,
                  reason:
                      'Disabled $id ${widget.runtimeType} must not remain actionable',
                );
              }
            }
          }
          if (state == 'hover') {
            expect(
              button.statesController!.value,
              contains(WidgetState.hovered),
            );
          }
          if (state == 'pressed') {
            expect(
              button.statesController!.value,
              contains(WidgetState.pressed),
            );
          }
          if (state == 'loading') {
            expect(find.byType(InlineProgress), findsWidgets);
          }
          if (state == 'offline') {
            expect(find.byType(OfflineBanner), findsWidgets);
          }
          expect(tester.takeException(), isNull);
        },
      );
    }
  }
}
