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
      actions: [
        TextButton(
          onPressed: () =>
              context.read<WeeklySummaryBloc>().add(const RefreshReport()),
          child: Text(l.refresh),
        ),
      ],
      children: [
        ReportView<WeeklySummary, WeeklySummaryBloc>(
          builder: (context, data) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                l.resolvedPeriod(
                  formatDate(data.start, l.localeName),
                  formatDate(data.end, l.localeName),
                ),
              ),
              for (final amount in data.lines)
                AmountView(
                  amount: amount,
                  label: amountLabel(l, amount.label),
                  hero: amount.label == 'recorded_cash_sales',
                  onTap: () => openEvidence(context, amount),
                ),
              const SizedBox(height: AppDimens.xl),
              SectionLabel(text: l.agingOldest),
              for (final debt in data.aging) ...[
                AmountView(
                  amount: debt.outstanding,
                  label: l.partyOption(debt.name, debt.id),
                  onTap: () => openEvidence(context, debt.outstanding),
                ),
                if (debt.days != null)
                  Text(
                    l.daysOverdue(
                      IqdFormatter.digits(debt.days.toString(), l.localeName),
                    ),
                  ),
              ],
              SecondaryButton(
                text: l.showAllDebts,
                onPressed: () => context.push('/debts'),
              ),
              const SizedBox(height: AppDimens.xl),
              SectionLabel(text: l.estimatedMargin),
              if (data.marginShown)
                AmountView(
                  amount: data.margin,
                  label: l.estimatedMargin,
                  onTap: () => openEvidence(context, data.margin),
                )
              else
                InfoStrip(text: l.insufficientMargin),
              Text(
                data.coverage == null
                    ? l.coverageMissing
                    : l.coverageValue(
                        IqdFormatter.digits(
                          data.coverage.toString(),
                          l.localeName,
                        ),
                      ),
              ),
              InfoStrip(text: l.marginExclusions),
              for (final flag in data.flags) ReviewFlagView(flag: flag),
              const SizedBox(height: AppDimens.lg),
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
