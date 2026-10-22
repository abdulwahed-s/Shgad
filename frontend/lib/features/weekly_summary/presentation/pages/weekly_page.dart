import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/amount_label.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/merchant_shell.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/report_view.dart';
import '../../../../core/widgets/review_flag_view.dart';
import '../../../../core/widgets/section_label.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/weekly_summary.dart';
import '../bloc/weekly_summary_bloc.dart';

class WeeklyPage extends StatelessWidget {
  const WeeklyPage({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<WeeklySummaryBloc>()..add(const RefreshReport()),
    child: const _WeeklyView(),
  );
}

class _WeeklyView extends StatelessWidget {
  const _WeeklyView();
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return MerchantPage(
      title: l.weeklyTitle,
      columns: true,
      onRefresh: () => refreshReport(context.read<WeeklySummaryBloc>()),
      children: [
        ReportView<WeeklySummary, WeeklySummaryBloc>(
          dateLabel: (d) => l.resolvedPeriod(
            formatDate(d.start, l.localeName),
            formatDate(d.end, l.localeName),
          ),
          builder: (context, data) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              ScreenColumns(
                start: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final amount in data.lines)
                      if (amount.label == 'recorded_cash_sales')
                        HeroCard(
                          amount: amount,
                          label: l.recordedCashSales,
                          onTap: () => openEvidence(context, amount),
                        ),
                    const SizedBox(height: AppDimens.lg),
                    for (final amount in data.lines)
                      if (amount.label == 'unexplained_cash_difference')
                        LedgerCard(
                          child: LedgerRow(
                            amount: amount,
                            label: l.unexplainedDifference,
                            onTap: () => openEvidence(context, amount),
                          ),
                        ),
                    const SizedBox(height: AppDimens.xl),
                    LedgerGroup(
                      title: l.weeklyTitle,
                      children: [
                        for (final (index, amount) in data.lines.indexed)
                          if (amount.label != 'recorded_cash_sales' &&
                              amount.label != 'unexplained_cash_difference')
                            LedgerRow(
                              amount: amount,
                              // The unchanged model preserves API field order;
                              // both live receivable fields use total_outstanding.
                              label: switch (index) {
                                8 => l.receivables,
                                9 => l.overdueReceivables,
                                _ => amountLabel(l, amount.label),
                              },
                              onTap: () => openEvidence(context, amount),
                            ),
                      ],
                    ),
                  ],
                ),
                end: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    LedgerGroup(
                      title: l.agingOldest,
                      children: [
                        if (data.aging.isEmpty) Text(l.noRecords),
                        for (final debt in data.aging)
                          LedgerRow(
                            amount: debt.outstanding,
                            label: l.partyOption(debt.name, debt.id),
                            caption: debt.days == null
                                ? null
                                : l.daysOverdue(
                                    IqdFormatter.digits(
                                      debt.days.toString(),
                                      l.localeName,
                                    ),
                                  ),
                            onTap: () =>
                                openEvidence(context, debt.outstanding),
                          ),
                      ],
                    ),
                    Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: TextAction(
                        text: l.showAllDebts,
                        onPressed: () => context.push('/debts'),
                      ),
                    ),
                    const SizedBox(height: AppDimens.xl),
                    SectionLabel(text: l.estimatedMargin),
                    LedgerCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          if (data.marginShown)
                            LedgerRow(
                              amount: data.margin,
                              label: l.estimatedMargin,
                              onTap: () => openEvidence(context, data.margin),
                            )
                          else
                            InfoStrip(text: l.insufficientMargin),
                          const SizedBox(height: AppDimens.sm),
                          Text(
                            data.coverage == null
                                ? l.coverageMissing
                                : l.coverageValue(
                                    IqdFormatter.digits(
                                      data.coverage.toString(),
                                      l.localeName,
                                    ),
                                  ),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                          const SizedBox(height: AppDimens.md),
                          InfoStrip(text: l.marginExclusions),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              if (data.flags.isNotEmpty) ...[
                const SizedBox(height: AppDimens.xl),
                for (final flag in data.flags) ReviewFlagView(flag: flag),
              ],
              const SizedBox(height: AppDimens.xl),
              InfoStrip(
                text: switch (data.suggestion) {
                  'review_unmatched_payment' => l.reviewUnmatched,
                  'review_duplicate_payment' => l.reviewDuplicate,
                  'review_debts' => l.reviewDebts,
                  _ => l.noActionNeeded,
                },
              ),
            ],
          ),
        ),
      ],
    );
  }
}
