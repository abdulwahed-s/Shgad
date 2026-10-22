import 'package:flutter/material.dart';
import '../constants/app_dimens.dart';

/// A keyboard-only ring around the existing Material focus target.
/// It adds no tab stop and does not change control geometry.
class FocusOutline extends StatefulWidget {
  const FocusOutline({
    required this.child,
    this.force = false,
    this.enabled = true,
    super.key,
  });
  final Widget child;
  final bool force, enabled;
  @override
  State<FocusOutline> createState() => _FocusOutlineState();
}

class _FocusOutlineState extends State<FocusOutline> {
  bool focused = false;
  @override
  Widget build(BuildContext context) => Focus(
    canRequestFocus: false,
    skipTraversal: true,
    onFocusChange: (value) => setState(() => focused = value),
    child: CustomPaint(
      foregroundPainter:
          widget.enabled &&
              (widget.force ||
                  InteractionPreview.of(
                    context,
                  ).contains(WidgetState.focused) ||
                  focused &&
                      FocusManager.instance.highlightMode ==
                          FocusHighlightMode.traditional)
          ? _FocusPainter(Theme.of(context).colorScheme.primary)
          : null,
      child: widget.child,
    ),
  );
}

class InteractionPreview extends InheritedWidget {
  const InteractionPreview({
    required this.states,
    required super.child,
    super.key,
  });
  final Set<WidgetState> states;
  static Set<WidgetState> of(BuildContext context) =>
      context
          .dependOnInheritedWidgetOfExactType<InteractionPreview>()
          ?.states ??
      const {};
  @override
  bool updateShouldNotify(InteractionPreview old) => old.states != states;
}

class _FocusPainter extends CustomPainter {
  const _FocusPainter(this.colour);
  final Color colour;
  @override
  void paint(Canvas canvas, Size size) {
    final rect = (Offset.zero & size).inflate(
      AppDimens.focusOffset + AppDimens.focusWidth / 2,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(AppDimens.radiusMd)),
      Paint()
        ..color = colour
        ..style = PaintingStyle.stroke
        ..strokeWidth = AppDimens.focusWidth,
    );
  }

  @override
  bool shouldRepaint(_FocusPainter old) => old.colour != colour;
}

/// Covers native Material focus targets (navigation, dialogs and pickers).
/// Shared controls draw their own ring; this layer never adds a tab stop.
class KeyboardFocusLayer extends StatefulWidget {
  const KeyboardFocusLayer({required this.child, super.key});
  final Widget child;
  @override
  State<KeyboardFocusLayer> createState() => _KeyboardFocusLayerState();
}

class _KeyboardFocusLayerState extends State<KeyboardFocusLayer>
    with WidgetsBindingObserver {
  final surface = GlobalKey();
  Rect? ring;
  bool scheduled = false;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    FocusManager.instance.addListener(schedule);
    FocusManager.instance.addHighlightModeListener(highlightChanged);
  }

  void highlightChanged(FocusHighlightMode _) => schedule();
  @override
  void didChangeMetrics() => schedule();
  void schedule() {
    if (!mounted || scheduled) return;
    scheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      scheduled = false;
      if (!mounted) return;
      Rect? next;
      final target = FocusManager.instance.primaryFocus?.context;
      var shared = false;
      target?.visitAncestorElements((element) {
        if (element.widget is FocusOutline) shared = true;
        return !shared;
      });
      final box = target?.findRenderObject();
      final root = surface.currentContext?.findRenderObject();
      if (!shared &&
          FocusManager.instance.primaryFocus is! FocusScopeNode &&
          FocusManager.instance.highlightMode ==
              FocusHighlightMode.traditional &&
          box is RenderBox &&
          box.attached &&
          box.hasSize &&
          root is RenderBox &&
          root.attached &&
          root.hasSize) {
        final offset = root.globalToLocal(box.localToGlobal(Offset.zero));
        final padding = AppDimens.focusOffset + AppDimens.focusWidth;
        next = Rect.fromLTRB(
          offset.dx.clamp(padding, root.size.width - padding),
          offset.dy.clamp(padding, root.size.height - padding),
          (offset.dx + box.size.width).clamp(
            padding,
            root.size.width - padding,
          ),
          (offset.dy + box.size.height).clamp(
            padding,
            root.size.height - padding,
          ),
        );
      }
      if (ring != next) setState(() => ring = next);
    });
    WidgetsBinding.instance.scheduleFrame();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    FocusManager.instance.removeListener(schedule);
    FocusManager.instance.removeHighlightModeListener(highlightChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      NotificationListener<ScrollNotification>(
        onNotification: (_) {
          schedule();
          return false;
        },
        child: Stack(
          key: surface,
          fit: StackFit.expand,
          children: [
            widget.child,
            if (ring != null)
              Positioned.fromRect(
                rect: ring!,
                child: IgnorePointer(
                  child: CustomPaint(
                    painter: _FocusPainter(
                      Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ),
              ),
          ],
        ),
      );
}
