import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/amount_label.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/page_header.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../bloc/forecast_bloc.dart';

String scenarioText(AppLocalizations l, String name) => switch (name) {
  'base' => l.scenarioBase,
  'conservative' => l.scenarioConservative,
  _ => l.scenarioStress,
};
String chartDate(String iso, String locale) =>
    IqdFormatter.digits(iso.substring(5).replaceAll('-', '/'), locale);

class ForecastPage extends StatelessWidget {
  const ForecastPage({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<ForecastBloc>()..add(const RefreshForecast()),
    child: const _ForecastView(),
  );
}

class _ForecastView extends StatelessWidget {
  const _ForecastView();
  @override
  Widget build(BuildContext context) =>
      BlocBuilder<ForecastBloc, ForecastState>(
        builder: (context, state) {
          final l = AppLocalizations.of(context);
          final v = state.view;
          final data = v.snapshot?.data;
          final selected = v.selected;
          final bloc = context.read<ForecastBloc>();
          return MerchantPage(
            title: l.forecastTitle,
            children: [
              if (v.snapshot != null) ...[
                if (v.snapshot!.offline)
                  OfflineBanner(updatedAt: v.snapshot!.updatedAt),
                PageMeta(
                  updated: v.snapshot!.offline
                      ? null
                      : l.updatedAt(
                          l.timeInBaghdad(
                            formatDate(
                              v.snapshot!.updatedAt,
                              l.localeName,
                              timestamp: true,
                            ),
                          ),
                        ),
                  date: data == null
                      ? null
                      : l.businessDate(formatDate(data.asOf, l.localeName)),
                  onRefresh: () => bloc.add(const RefreshForecast()),
                ),
              ],
              if (state is ForecastLoading || state is ForecastInitial)
                const InlineProgress(),
              if (state is ForecastFailure)
                FailureView(
                  failure: state.failure,
                  onRetry: () => bloc.add(const RefreshForecast()),
                ),
              if (data != null && selected != null) ...[
                HeroCard(
                  label: l.forecastFirstShort,
                  sentence: selected.shortfall == null
                      ? l.forecastNoShort
                      : formatDate(selected.shortfall!, l.localeName),
                ),
                const SizedBox(height: AppDimens.lg),
                SegmentedControl(
                  choices: {
                    'base': l.scenarioBase,
                    'conservative': l.scenarioConservative,
                    'stress': l.scenarioStress,
                  },
                  selected: v.scenario,
                  onSelected: (name) => bloc.add(ChooseScenario(name)),
                ),
                const SizedBox(height: AppDimens.lg),
                LedgerCard(
                  child: Semantics(
                    image: true,
                    label: [
                      l.chartDescription,
                      scenarioText(l, v.scenario),
                      selected.shortfall == null
                          ? l.forecastNoShort
                          : l.forecastFirstShort +
                                formatDate(selected.shortfall!, l.localeName),
                    ].join('. '),
                    child: ExcludeSemantics(
                      child: SizedBox(
                        height: AppDimens.chartHeight,
                        child: CustomPaint(
                          painter: ForecastPainter(
                            v.trace!,
                            Theme.of(context).colorScheme,
                            labels: [
                              chartDate(selected.days.first.date, l.localeName),
                              chartDate(
                                selected.days[selected.days.length ~/ 2].date,
                                l.localeName,
                              ),
                              chartDate(selected.days.last.date, l.localeName),
                            ],
                            zero: IqdFormatter.digits('0', l.localeName),
                            style: Theme.of(context).textTheme.bodySmall!,
                            textScaler: MediaQuery.textScalerOf(context),
                            shortfall: selected.shortfall == null
                                ? null
                                : chartDate(selected.shortfall!, l.localeName),
                            rtl:
                                Directionality.of(context) == TextDirection.rtl,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: AppDimens.xl),
                LedgerGroup(
                  title: l.topInflows,
                  children: [
                    for (final amount in selected.inflows)
                      LedgerRow(
                        amount: amount,
                        label: amountLabel(l, amount.label, projected: true),
                        onTap: () => openEvidence(context, amount),
                      ),
                  ],
                ),
                const SizedBox(height: AppDimens.xl),
                LedgerGroup(
                  title: l.topOutflows,
                  children: [
                    for (final amount in selected.outflows)
                      LedgerRow(
                        amount: amount,
                        label: amountLabel(l, amount.label, projected: true),
                        onTap: () => openEvidence(context, amount),
                      ),
                  ],
                ),
                const SizedBox(height: AppDimens.xl),
                InfoStrip(text: l.estimateOnly, expected: true),
                const SizedBox(height: AppDimens.md),
                ExpansionTile(
                  title: Text(l.expectedNotice),
                  children: [
                    for (final note in [
                      l.assumptionSales,
                      l.assumptionDifference,
                      l.assumptionOverdue,
                      l.assumptionLateness,
                      l.assumptionStress,
                      l.assumptionCosts,
                      l.assumptionSupplier,
                    ])
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppDimens.sm),
                        child: InfoStrip(text: note),
                      ),
                  ],
                ),
                const SizedBox(height: AppDimens.xl),
                ledgerDropdown<String>(
                  context,
                  key: ValueKey('day_${v.scenario}'),
                  initialValue: v.day!.date,
                  decoration: InputDecoration(labelText: l.forecastDay),
                  items: [
                    for (final day in selected.days)
                      DropdownMenuItem(
                        value: day.date,
                        child: Text(formatDate(day.date, l.localeName)),
                      ),
                  ],
                  onChanged: (value) {
                    if (value != null) {
                      bloc.add(ChooseForecastDay(value));
                    }
                  },
                ),
                LedgerGroup(
                  children: [
                    LedgerRow(
                      amount: v.dayAmount('closing'),
                      label: l.estimatedClosing,
                      exact: true,
                    ),
                    LedgerRow(
                      amount: v.dayAmount('sales'),
                      label: l.recordedSalesDriver,
                      exact: true,
                    ),
                    LedgerRow(
                      amount: v.dayAmount('difference'),
                      label: l.differenceDriver,
                      exact: true,
                    ),
                  ],
                ),
                for (final amount in data.overdue)
                  LedgerRow(
                    amount: amount,
                    label: l.overdueExcluded,
                    onTap: () => openEvidence(context, amount),
                  ),
              ],
            ],
          );
        },
      );
}

/// Every operation below is normalized chart geometry, never IQD arithmetic.
class ForecastPainter extends CustomPainter {
  ForecastPainter(
    this.trace,
    this.colors, {
    required this.labels,
    required this.zero,
    required this.style,
    required this.rtl,
    required this.textScaler,
    this.shortfall,
  });
  final ChartTrace trace;
  final ColorScheme colors;
  final List<String> labels;
  final String zero;
  final TextStyle style;
  final bool rtl;
  final TextScaler textScaler;
  final String? shortfall;
  @override
  void paint(Canvas canvas, Size size) {
    final bounds = Rect.fromLTRB(
      AppDimens.xl,
      AppDimens.lg,
      size.width - AppDimens.sm,
      size.height - AppDimens.xxl,
    );
    Offset pixel(ChartPoint p) => Offset(
      bounds.left + (rtl ? 1 - p.x : p.x) * bounds.width,
      bounds.top + p.y * bounds.height,
    );
    final zeroY = bounds.top + trace.zeroY * bounds.height;
    final zeroPaint = Paint()
      ..color = colors.outlineVariant
      ..strokeWidth = AppDimens.borderWidth;
    for (double x = bounds.left; x < bounds.right; x += AppDimens.md) {
      canvas.drawLine(
        Offset(x, zeroY),
        Offset(math.min(x + AppDimens.xs, bounds.right), zeroY),
        zeroPaint,
      );
    }
    void text(String value, double x, double y, {Color? colour}) {
      final p = TextPainter(
        text: TextSpan(
          text: value,
          style: style.copyWith(color: colour ?? style.color),
        ),
        textDirection: TextDirection.ltr,
        textScaler: textScaler,
      )..layout();
      p.paint(
        canvas,
        Offset(
          x.clamp(0, math.max(0, size.width - p.width)),
          y.clamp(0, math.max(0, size.height - p.height)),
        ),
      );
    }

    text(zero, 0, zeroY - AppDimens.sm);
    final paint = Paint()
      ..strokeWidth = AppDimens.progressHeight
      ..style = PaintingStyle.stroke;
    for (var i = 1; i < trace.points.length; i++) {
      final a = trace.points[i - 1], b = trace.points[i];
      final pa = pixel(a), pb = pixel(b);
      final belowA = a.y > trace.zeroY, belowB = b.y > trace.zeroY;
      if (belowA == belowB) {
        canvas.drawLine(
          pa,
          pb,
          paint..color = belowA ? colors.error : colors.primary,
        );
      } else {
        final cross = Offset.lerp(pa, pb, (trace.zeroY - a.y) / (b.y - a.y))!;
        canvas.drawLine(
          pa,
          cross,
          paint..color = belowA ? colors.error : colors.primary,
        );
        canvas.drawLine(
          cross,
          pb,
          paint..color = belowB ? colors.error : colors.primary,
        );
      }
    }
    for (var i = 0; i < labels.length; i++) {
      final x = bounds.left + (rtl ? 1 - i / 2 : i / 2) * bounds.width;
      text(
        labels[i],
        x -
            (i == 1
                ? AppDimens.xl
                : rtl && i == 0 || !rtl && i == 2
                ? AppDimens.xxxl
                : 0),
        size.height - AppDimens.xl,
      );
    }
    if (trace.shortfallIndex != null) {
      final p = pixel(trace.points[trace.shortfallIndex!]);
      canvas.drawLine(
        p,
        Offset(p.dx, bounds.bottom),
        Paint()
          ..color = colors.error
          ..strokeWidth = AppDimens.borderWidth,
      );
      canvas.drawCircle(
        p,
        AppDimens.chartMarkerRadius,
        Paint()..color = colors.error,
      );
      if (shortfall != null) {
        text(shortfall!, p.dx, p.dy - AppDimens.xl, colour: colors.error);
      }
    }
  }

  @override
  bool shouldRepaint(ForecastPainter old) =>
      old.trace != trace ||
      old.colors != colors ||
      old.labels != labels ||
      old.rtl != rtl ||
      old.textScaler != textScaler;
}
