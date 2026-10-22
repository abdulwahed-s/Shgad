import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/utils/date_formatter.dart';
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
              DebtSectionView(
                section: data.receivables,
                title: l.receivables,
                payable: false,
              ),
              const Divider(),
              DebtSectionView(
                section: data.payables,
                title: l.payables,
                payable: true,
              ),
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
    required this.payable,
    super.key,
  });
  final DebtSection section;
  final String title;
  final bool payable;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionLabel(text: title),
        Text(l.businessDate(formatDate(section.asOf, l.localeName))),
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
                      : l.dueAt(formatDate(obligation.due!, l.localeName)),
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
                SecondaryButton(
                  text: payable ? l.partialPayment : l.partialCollection,
                  onPressed: () => context.push(
                    Uri(
                      path: '/entry',
                      queryParameters: {
                        'type': payable
                            ? 'SUPPLIER_PAYMENT'
                            : 'CREDIT_COLLECTION',
                        'counterparty_id': party.id,
                        'obligation_id': obligation.id,
                        'business_date': section.asOf,
                      },
                    ).toString(),
                  ),
                ),
              ],
            ],
          ),
      ],
    );
  }
}
