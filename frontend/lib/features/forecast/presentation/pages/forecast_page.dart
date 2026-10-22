import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/amount_label.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/section_label.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../bloc/forecast_bloc.dart';

String scenarioText(AppLocalizations l, String name) => switch (name) {
  'base' => l.scenarioBase,
  'conservative' => l.scenarioConservative,
  _ => l.scenarioStress,
};

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
            actions: [
              TextButton(
                onPressed: () => bloc.add(const RefreshForecast()),
                child: Text(l.refresh),
              ),
            ],
            children: [
              if (state is ForecastLoading || state is ForecastInitial)
                const LinearProgressIndicator(),
              if (state is ForecastFailure)
                FailureView(
                  failure: state.failure,
                  onRetry: () => bloc.add(const RefreshForecast()),
                ),
              if (data != null && selected != null) ...[
                if (v.snapshot!.offline)
                  OfflineBanner(updatedAt: v.snapshot!.updatedAt)
                else
                  Text(
                    l.updatedAt(
                      l.timeInBaghdad(
                        formatDate(
                          v.snapshot!.updatedAt,
                          l.localeName,
                          timestamp: true,
                        ),
                      ),
                    ),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                SectionLabel(text: l.forecastFirstShort),
                Text(
                  selected.shortfall == null
                      ? l.forecastNoShort
                      : formatDate(selected.shortfall!, l.localeName),
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const StatusLabel(kind: 'expected'),
                const SizedBox(height: AppDimens.md),
                Wrap(
                  spacing: AppDimens.sm,
                  runSpacing: AppDimens.sm,
                  children: [
                    for (final name in ['base', 'conservative', 'stress'])
                      ChoiceChip(
                        label: Text(scenarioText(l, name)),
                        selected: v.scenario == name,
                        onSelected: (_) => bloc.add(ChooseScenario(name)),
                      ),
                  ],
                ),
                const SizedBox(height: AppDimens.lg),
                Semantics(
                  label: l.chartDescription,
                  child: SizedBox(
                    height: AppDimens.chartHeight,
                    child: CustomPaint(
                      painter: ForecastPainter(
                        v.trace!,
                        Theme.of(context).colorScheme,
                      ),
                    ),
                  ),
                ),
                InfoStrip(text: l.estimateOnly, expected: true),
                const SizedBox(height: AppDimens.xl),
                SectionLabel(text: l.topInflows),
                for (final amount in selected.inflows)
                  AmountView(
                    amount: amount,
                    label: amountLabel(l, amount.label, projected: true),
                    onTap: () => openEvidence(context, amount),
                  ),
                SectionLabel(text: l.topOutflows),
                for (final amount in selected.outflows)
                  AmountView(
                    amount: amount,
                    label: amountLabel(l, amount.label, projected: true),
                    onTap: () => openEvidence(context, amount),
                  ),
                const SizedBox(height: AppDimens.xl),
                DropdownButtonFormField<String>(
                  key: ValueKey('day_${v.scenario}'),
                  initialValue: v.day!.date,
                  isExpanded: true,
                  decoration: InputDecoration(labelText: l.forecastDay),
                  items: [
                    for (final day in selected.days)
                      DropdownMenuItem(
                        value: day.date,
                        child: Text(formatDate(day.date, l.localeName)),
                      ),
                  ],
                  onChanged: (value) {
                    if (value != null) bloc.add(ChooseForecastDay(value));
                  },
                ),
                AmountView(
                  amount: v.dayAmount('closing'),
                  label: l.estimatedClosing,
                  exact: true,
                ),
                AmountView(
                  amount: v.dayAmount('sales'),
                  label: l.recordedSalesDriver,
                  exact: true,
                ),
                AmountView(
                  amount: v.dayAmount('difference'),
                  label: l.differenceDriver,
                  exact: true,
                ),
                InfoStrip(text: l.assumptionSales),
                InfoStrip(text: l.assumptionDifference),
                InfoStrip(text: l.assumptionOverdue),
                InfoStrip(text: l.assumptionLateness),
                InfoStrip(text: l.assumptionStress),
                InfoStrip(text: l.assumptionCosts),
                InfoStrip(text: l.assumptionSupplier),
                for (final amount in data.overdue)
                  AmountView(
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

class ForecastPainter extends CustomPainter {
  ForecastPainter(this.trace, this.colors);
  final ChartTrace trace;
  final ColorScheme colors;
  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = colors.primary
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    final zero = Paint()
      ..color = colors.outline
      ..strokeWidth = 1;
    final bounds = Rect.fromLTWH(8, 8, size.width - 16, size.height - 16);
    Offset pixel(ChartPoint point) => Offset(
      bounds.left + point.x * bounds.width,
      bounds.top + point.y * bounds.height,
    );
    canvas.drawLine(
      Offset(bounds.left, bounds.top + trace.zeroY * bounds.height),
      Offset(bounds.right, bounds.top + trace.zeroY * bounds.height),
      zero,
    );
    final path = Path();
    for (var i = 0; i < trace.points.length; i++) {
      final p = pixel(trace.points[i]);
      if (i == 0) {
        path.moveTo(p.dx, p.dy);
      } else {
        path.lineTo(p.dx, p.dy);
      }
    }
    canvas.drawPath(path, line);
    if (trace.shortfallIndex != null) {
      canvas.drawCircle(
        pixel(trace.points[trace.shortfallIndex!]),
        4,
        Paint()..color = colors.error,
      );
    }
  }

  @override
  bool shouldRepaint(ForecastPainter oldDelegate) =>
      oldDelegate.trace != trace || oldDelegate.colors != colors;
}
