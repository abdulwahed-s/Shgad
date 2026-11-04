import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/domain/evidence_request.dart';
import '../../../../core/domain/snapshot.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/collections.dart';
import '../bloc/collections_bloc.dart';

class MorningBriefCard extends StatelessWidget {
  const MorningBriefCard({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<MorningBriefBloc>()..add(const RefreshReport()),
    child: const _BriefCardView(),
  );
}

class _BriefCardView extends StatelessWidget {
  const _BriefCardView();
  @override
  Widget build(BuildContext context) =>
      BlocBuilder<MorningBriefBloc, ReportState<MorningBriefData>>(
        builder: (context, state) {
          final l = AppLocalizations.of(context);
          final Snapshot<MorningBriefData>? snapshot = switch (state) {
            ReportLoaded<MorningBriefData>(:final snapshot) ||
            ReportOffline<MorningBriefData>(:final snapshot) => snapshot,
            ReportLoading<MorningBriefData>(:final previous) => previous,
            _ => null,
          };
          final data = snapshot?.data;
          return LedgerGroup(
            title: l.morningBriefTitle,
            caption: data == null
                ? null
                : l.resolvedPeriod(
                    formatDate(data.weekStart, l.localeName),
                    formatDate(data.weekEnd, l.localeName),
                  ),
            children: [
              if (state is ReportInitial<MorningBriefData> ||
                  state is ReportLoading<MorningBriefData>)
                const InlineProgress(),
              if (state is ReportFailure<MorningBriefData>)
                FailureView(
                  failure: state.failure,
                  onRetry: () => context.read<MorningBriefBloc>().add(
                    const RefreshReport(),
                  ),
                ),
              if (snapshot?.offline == true)
                OfflineBanner(updatedAt: snapshot!.updatedAt),
              if (data != null) ...[
                LedgerRow(
                  amount: data.duesToday,
                  label: l.briefDuesToday,
                  onTap: () => openEvidence(context, data.duesToday),
                ),
                LedgerRow(
                  amount: data.duesWeek,
                  label: l.briefDuesWeek,
                  onTap: () => openEvidence(context, data.duesWeek),
                ),
                LedgerRow(
                  amount: data.overdue,
                  label: l.briefOverdueTotal,
                  onTap: () => openEvidence(context, data.overdue),
                ),
                BriefCountRow(
                  label: l.briefOverdueCustomers,
                  count: data.customerCount,
                ),
                BriefCountRow(label: l.briefOpenFlags, count: data.flagsCount),
                if (data.topCustomers.isNotEmpty)
                  Text(
                    data.topCustomers.map((p) => p.name).join('، '),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                const SizedBox(height: AppDimens.md),
                SecondaryButton(
                  text: l.briefCollect,
                  onPressed: () => context.push('/collections'),
                ),
              ],
            ],
          );
        },
      );
}

class BriefCountRow extends StatelessWidget {
  const BriefCountRow({required this.label, required this.count, super.key});
  final String label;
  final CountEvidence count;
  @override
  Widget build(BuildContext context) => TextAction(
    text:
        '$label: ${IqdFormatter.digits(count.value.toString(), AppLocalizations.of(context).localeName)}',
    onPressed: () => context.push(
      '/evidence',
      extra: EvidenceRequest(
        count.sources,
        count.formula,
        queryEvidence: count.proof,
      ),
    ),
  );
}
