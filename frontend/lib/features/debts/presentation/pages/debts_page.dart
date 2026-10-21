import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/report_view.dart';
import '../../../../core/widgets/section_label.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/debts.dart';
import '../bloc/debts_bloc.dart';

class DebtsPage extends StatelessWidget {
  const DebtsPage({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<DebtsBloc>()..add(const RefreshReport()),
    child: const _DebtsView(),
  );
}

class _DebtsView extends StatelessWidget {
  const _DebtsView();
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return MerchantPage(
      title: l.debtsTitle,
      actions: [
        TextButton(
          onPressed: () => context.read<DebtsBloc>().add(const RefreshReport()),
          child: Text(l.refresh),
        ),
      ],
      children: [
        ReportView<Debts, DebtsBloc>(
          builder: (context, data) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              DebtSectionView(section: data.receivables, title: l.receivables),
              const Divider(),
              DebtSectionView(section: data.payables, title: l.payables),
            ],
          ),
        ),
      ],
    );
  }
}

class DebtSectionView extends StatelessWidget {
  const DebtSectionView({
    required this.section,
    required this.title,
    super.key,
  });
  final DebtSection section;
  final String title;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionLabel(text: title),
        Text(l.businessDate(section.asOf)),
        AmountView(
          amount: section.total,
          label: title,
          hero: true,
          onTap: () => openEvidence(context, section.total),
        ),
        if (section.parties.isEmpty) InfoStrip(text: l.noRecords),
        for (final party in section.parties)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text(party.name),
            subtitle: Text(party.id),
            children: [
              AmountView(
                amount: party.outstanding,
                label: l.outstanding,
                onTap: () => openEvidence(context, party.outstanding),
              ),
              for (final obligation in party.obligations) ...[
                const Divider(),
                Text(obligation.id),
                Text(
                  obligation.due == null
                      ? l.errorDueDate
                      : l.dueAt(obligation.due!),
                ),
                AmountView(
                  amount: obligation.original,
                  label: l.originalAmount,
                  onTap: () => openEvidence(context, obligation.original),
                ),
                AmountView(
                  amount: obligation.outstanding,
                  label: l.outstanding,
                  onTap: () => openEvidence(context, obligation.outstanding),
                ),
                if (obligation.collections.isNotEmpty)
                  Text(l.paymentSources(obligation.collections.join(', '))),
              ],
            ],
          ),
      ],
    );
  }
}
