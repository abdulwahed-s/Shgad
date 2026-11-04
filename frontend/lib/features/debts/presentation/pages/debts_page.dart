import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/form_fields.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/merchant_shell.dart';
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

class _DebtsView extends StatefulWidget {
  const _DebtsView();
  @override
  State<_DebtsView> createState() => _DebtsViewState();
}

class _DebtsViewState extends State<_DebtsView> {
  String selected = 'customers';
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final expanded =
        MediaQuery.sizeOf(context).width >= AppDimens.expandedBreakpoint;
    return MerchantPage(
      title: l.debtsTitle,
      columns: true,
      onRefresh: () => refreshReport(context.read<DebtsBloc>()),
      children: [
        ReportView<Debts, DebtsBloc>(
          dateLabel: (d) =>
              l.businessDate(formatDate(d.receivables.asOf, l.localeName)),
          builder: (context, data) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              LedgerGroup(
                children: [
                  LedgerRow(
                    amount: data.receivables.total,
                    label: l.receivables,
                    onTap: () => openEvidence(context, data.receivables.total),
                  ),
                  LedgerRow(
                    amount: data.payables.total,
                    label: l.payables,
                    onTap: () => openEvidence(context, data.payables.total),
                  ),
                ],
              ),
              const SizedBox(height: AppDimens.xl),
              TextAction(
                text: l.collectionsTitle,
                onPressed: () => context.push('/collections'),
              ),
              const SizedBox(height: AppDimens.md),
              if (expanded)
                ScreenColumns(
                  start: DebtSectionView(
                    section: data.receivables,
                    title: l.receivables,
                    payable: false,
                  ),
                  end: DebtSectionView(
                    section: data.payables,
                    title: l.payables,
                    payable: true,
                  ),
                )
              else ...[
                SegmentedControl(
                  choices: {
                    'customers': l.debtCustomers,
                    'suppliers': l.debtSuppliers,
                  },
                  selected: selected,
                  onSelected: (value) => setState(() => selected = value),
                ),
                const SizedBox(height: AppDimens.lg),
                DebtSectionView(
                  section: selected == 'customers'
                      ? data.receivables
                      : data.payables,
                  title: selected == 'customers' ? l.receivables : l.payables,
                  payable: selected == 'suppliers',
                ),
              ],
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
        if (section.parties.isEmpty)
          InfoStrip(text: l.noRecords)
        else
          LedgerGroup(
            children: [
              for (final party in section.parties)
                ExpansionTile(
                  key: ValueKey(party.id),
                  title: IgnorePointer(
                    child: LedgerRow(
                      amount: party.outstanding,
                      label: party.name,
                      interactive: true,
                      caption: [
                        party.id,
                        if (party.due != null)
                          l.dueAt(formatDate(party.due!, l.localeName)),
                      ].join(' · '),
                    ),
                  ),
                  children: [
                    TextAction(
                      text: l.evidence,
                      onPressed: () => openEvidence(context, party.outstanding),
                    ),
                    for (final obligation in party.obligations) ...[
                      const Divider(),
                      const SizedBox(height: AppDimens.md),
                      SelectableCaption(
                        obligation.id,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      LedgerRow(
                        amount: obligation.outstanding,
                        label: l.outstanding,
                        caption: obligation.due == null
                            ? l.errorDueDate
                            : l.dueAt(
                                formatDate(obligation.due!, l.localeName),
                              ),
                        secondary:
                            '${l.originalAmount} · ${obligation.original.value == null ? l.missing : IqdFormatter.format(obligation.original.value!, l.localeName, l.thousand, l.iqd)}',
                        onTap: () =>
                            openEvidence(context, obligation.outstanding),
                      ),
                      TextAction(
                        text: l.originalAmount,
                        onPressed: () =>
                            openEvidence(context, obligation.original),
                      ),
                      if (obligation.collections.isNotEmpty)
                        Text(
                          l.paymentSources(obligation.collections.join(', ')),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      TextAction(
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
          ),
      ],
    );
  }
}
