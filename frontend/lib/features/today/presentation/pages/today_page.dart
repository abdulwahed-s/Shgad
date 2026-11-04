import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/merchant_shell.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/report_view.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/today.dart';
import '../bloc/today_bloc.dart';
import '../../../collections/presentation/widgets/morning_brief_card.dart';

class TodayPage extends StatelessWidget {
  const TodayPage({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<TodayBloc>()..add(const RefreshReport()),
    child: const _TodayView(),
  );
}

class _TodayView extends StatelessWidget {
  const _TodayView();
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return MerchantPage(
      title: l.todayTitle,
      columns: true,
      onRefresh: () => refreshReport(context.read<TodayBloc>()),
      children: [
        ReportView<Today, TodayBloc>(
          dateLabel: (data) =>
              l.businessDate(formatDate(data.asOf, l.localeName)),
          builder: (context, data) => ScreenColumns(
            start: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                HeroCard(
                  amount: data.cash,
                  label: l.cashOnHand,
                  caption: data.countedAt == null
                      ? l.countMissing
                      : l.countedAt(
                          l.timeInBaghdad(
                            formatDate(
                              data.countedAt!,
                              l.localeName,
                              timestamp: true,
                            ),
                          ),
                        ),
                  onTap: () => openEvidence(context, data.cash),
                ),
                const SizedBox(height: AppDimens.lg),
                const MorningBriefCard(),
                const SizedBox(height: AppDimens.lg),
                ActionGroup(
                  children: [
                    PrimaryButton(
                      text: data.cash.value == null
                          ? l.useSample
                          : l.entryTitle,
                      onPressed: () => context.push(
                        data.cash.value == null ? '/sample' : '/entry',
                      ),
                    ),
                    SecondaryButton(
                      text: l.closeTitle,
                      onPressed: () => context.push('/close'),
                    ),
                  ],
                ),
              ],
            ),
            end: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                LedgerGroup(
                  title: l.upcomingTitle,
                  caption: l.resolvedPeriod(
                    formatDate(data.start, l.localeName),
                    formatDate(data.end, l.localeName),
                  ),
                  children: [
                    LedgerRow(
                      amount: data.dues,
                      label: l.supplierDues,
                      onTap: () => openEvidence(context, data.dues),
                    ),
                    LedgerRow(
                      amount: data.expected,
                      label: l.expectedCollections,
                      onTap: () => openEvidence(context, data.expected),
                    ),
                    LedgerRow(
                      amount: data.confirmed,
                      label: l.positionConfirmedShort,
                      onTap: () => openEvidence(context, data.confirmed),
                    ),
                    LedgerRow(
                      amount: data.withExpected,
                      label: l.positionExpectedShort,
                      onTap: () => openEvidence(context, data.withExpected),
                    ),
                  ],
                ),
                const SizedBox(height: AppDimens.sm),
                Text(
                  l.firstShortConfirmed(
                    data.firstConfirmed == null
                        ? l.noShortfall
                        : formatDate(data.firstConfirmed!, l.localeName),
                  ),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: AppDimens.xs),
                Text(
                  l.firstShortExpected(
                    data.firstExpected == null
                        ? l.noShortfall
                        : formatDate(data.firstExpected!, l.localeName),
                  ),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (data.dueItems.isNotEmpty)
                  ExpansionTile(
                    title: Text(l.supplierDues),
                    children: [
                      for (final item in data.dueItems)
                        LedgerRow(
                          amount: item.amount,
                          label: item.name,
                          caption: item.dueNow
                              ? l.dueNow
                              : l.dueAt(formatDate(item.dueDate, l.localeName)),
                          onTap: () => openEvidence(context, item.amount),
                        ),
                    ],
                  ),
                const SizedBox(height: AppDimens.lg),
                InfoStrip(text: l.expectedNotice, expected: true),
                if (data.overdue.isNotEmpty) ...[
                  const SizedBox(height: AppDimens.xl),
                  LedgerGroup(
                    title: l.overdueReceivables,
                    caption: l.overdueExcluded,
                    children: [
                      for (final item in data.overdue)
                        LedgerRow(
                          amount: item.amount,
                          label: item.name,
                          caption: l.dueAt(
                            formatDate(item.dueDate, l.localeName),
                          ),
                          onTap: () => openEvidence(context, item.amount),
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ],
    );
  }
}
