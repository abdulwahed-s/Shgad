import 'package:flutter/material.dart';

/// Balances short, localized sentences at word boundaries, preserving their
/// original semantics and type scale. Never used to alter a rendered LLM reply.
class BalancedText extends StatelessWidget {
  const BalancedText(this.text, {this.style, super.key});
  final String text;
  final TextStyle? style;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, bounds) {
      final effective = style ?? DefaultTextStyle.of(context).style;
      final painter = TextPainter(
        text: TextSpan(text: text, style: effective),
        textDirection: Directionality.of(context),
        textScaler: MediaQuery.textScalerOf(context),
      );
      painter.layout(maxWidth: bounds.maxWidth);
      final lines = painter.computeLineMetrics().length;
      double balancedWidth = bounds.maxWidth;
      if (lines > 1 && bounds.maxWidth.isFinite) {
        // Find the narrowest measure that preserves the natural line count,
        // then compare nearby measures. This also balances three/four-line
        // approved sentences without inserting newlines or changing their text.
        var low = 0.0;
        var high = bounds.maxWidth;
        for (var i = 0; i < 14; i++) {
          final middle = (low + high) / 2;
          painter.layout(maxWidth: middle);
          if (painter.computeLineMetrics().length > lines) {
            low = middle;
          } else {
            high = middle;
          }
        }
        double best = double.infinity;
        for (var i = 0; i <= 24; i++) {
          final measure = high + (bounds.maxWidth - high) * i / 24;
          painter.layout(maxWidth: measure);
          final metrics = painter.computeLineMetrics();
          if (metrics.length != lines) continue;
          final last = painter.getLineBoundary(
            TextPosition(offset: text.length - 1),
          );
          final orphan =
              text
                      .substring(last.start, last.end)
                      .trim()
                      .split(RegExp(r'\s+'))
                      .length ==
                  1
              ? bounds.maxWidth * 2
              : 0.0;
          final widest = metrics.fold<double>(
            0,
            (width, line) => line.width > width ? line.width : width,
          );
          final cost =
              metrics.fold<double>(
                0,
                (sum, line) => sum + (widest - line.width).abs(),
              ) +
              orphan;
          if (cost < best) {
            best = cost;
            balancedWidth = measure;
          }
        }
      }
      painter.dispose();
      return Align(
        alignment: AlignmentDirectional.centerStart,
        child: SizedBox(
          width: balancedWidth,
          child: Text(text, style: effective),
        ),
      );
    },
  );
}
