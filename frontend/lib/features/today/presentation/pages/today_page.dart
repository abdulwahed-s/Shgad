import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/report_view.dart';
import '../../../../core/widgets/section_label.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/today.dart';
import '../bloc/today_bloc.dart';

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
      actions: [
        TextButton(
          onPressed: () => context.read<TodayBloc>().add(const RefreshReport()),
          child: Text(l.refresh),
        ),
      ],
      children: [
        ReportView<Today, TodayBloc>(
          builder: (context, data) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SectionLabel(
                text: l.businessDate(formatDate(data.asOf, l.localeName)),
              ),
              LedgerCard(
                child: AmountView(
                  amount: data.cash,
                  label: l.cashOnHand,
                  hero: true,
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
              ),
              const SizedBox(height: AppDimens.md),
              PrimaryButton(
                text: data.cash.value == null ? l.useSample : l.entryTitle,
                onPressed: () => context.push(
                  data.cash.value == null ? '/sample' : '/entry',
                ),
              ),
              SecondaryButton(
                text: l.closeTitle,
                onPressed: () => context.push('/close'),
              ),
              const SizedBox(height: AppDimens.xl),
              SectionLabel(
                text: l.upcomingRange(
                  formatDate(data.start, l.localeName),
                  formatDate(data.end, l.localeName),
                ),
              ),
              AmountView(
                amount: data.dues,
                label: l.supplierDues,
                onTap: () => openEvidence(context, data.dues),
              ),
              AmountView(
                amount: data.expected,
                label: l.expectedCollections,
                onTap: () => openEvidence(context, data.expected),
              ),
              InfoStrip(text: l.expectedNotice, expected: true),
              AmountView(
                amount: data.confirmed,
                label: l.positionConfirmed,
                onTap: () => openEvidence(context, data.confirmed),
              ),
              AmountView(
                amount: data.withExpected,
                label: l.positionExpected,
                onTap: () => openEvidence(context, data.withExpected),
              ),
              Text(
                l.firstShortConfirmed(
                  data.firstConfirmed == null
                      ? l.noShortfall
                      : formatDate(data.firstConfirmed!, l.localeName),
                ),
              ),
              Text(
                l.firstShortExpected(
                  data.firstExpected == null
                      ? l.noShortfall
                      : formatDate(data.firstExpected!, l.localeName),
                ),
              ),
              for (final item in data.dueItems) ...[
                const Divider(),
                Text(item.name),
                Text(l.dueAt(formatDate(item.dueDate, l.localeName))),
                if (item.dueNow) Text(l.dueNow),
                AmountView(
                  amount: item.amount,
                  label: l.supplierDues,
                  onTap: () => openEvidence(context, item.amount),
                ),
              ],
              if (data.overdue.isNotEmpty)
                SectionLabel(text: l.overdueExcluded),
              for (final item in data.overdue)
                AmountView(
                  amount: item.amount,
                  label: item.name,
                  caption: l.dueAt(formatDate(item.dueDate, l.localeName)),
                  onTap: () => openEvidence(context, item.amount),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
