import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/presentation/report_bloc.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/utils/iqd_formatter.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/open_evidence.dart';
import '../../../../core/widgets/report_view.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../../domain/entities/collections.dart';
import '../bloc/collections_bloc.dart';
import '../widgets/draft_sheet.dart';

class CollectionsPage extends StatefulWidget {
  const CollectionsPage({this.customerId, this.tone = 'gentle', super.key});
  final String? customerId;
  final String tone;
  @override
  State<CollectionsPage> createState() => _CollectionsPageState();
}

class _CollectionsPageState extends State<CollectionsPage> {
  late final CollectionsBloc _bloc;
  @override
  void initState() {
    super.initState();
    _bloc = getIt<CollectionsBloc>();
    if (widget.customerId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        if (mounted) {
          await openReminderSheet(context, widget.customerId!, widget.tone);
          if (mounted) _bloc.add(const RefreshReport());
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => _bloc..add(const RefreshReport()),
    child: const _CollectionsView(),
  );
}

class _CollectionsView extends StatelessWidget {
  const _CollectionsView();
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return MerchantPage(
      title: l.collectionsTitle,
      onRefresh: () => refreshReport(context.read<CollectionsBloc>()),
      children: [
        Text(l.collectionsIntro, style: Theme.of(context).textTheme.bodyLarge),
        const SizedBox(height: AppDimens.lg),
        ReportView<Collections, CollectionsBloc>(
          dateLabel: (d) => l.businessDate(formatDate(d.asOf, l.localeName)),
          builder: (context, data) => data.items.isEmpty
              ? InfoStrip(
                  key: const ValueKey('collections_empty'),
                  text: l.collectionsEmpty,
                )
              : LedgerGroup(
                  children: [
                    for (final p in data.items) ...[
                      Text(
                        p.name,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      LedgerRow(
                        amount: p.overdue,
                        label: l.collectionOverdueAmount,
                        onTap: () => openEvidence(context, p.overdue),
                      ),
                      Text(
                        l.daysOverdue(
                          IqdFormatter.digits(
                            p.daysOverdue.toString(),
                            l.localeName,
                          ),
                        ),
                      ),
                      Text(
                        l.dueAt(formatDate(p.oldestDue, l.localeName)),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      Text(
                        p.lastReminderDate == null
                            ? l.collectionNeverReminded
                            : l.collectionLastReminded(
                                formatDate(p.lastReminderDate!, l.localeName),
                              ),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      TextAction(
                        key: ValueKey('draft_${p.id}'),
                        text: l.collectionPrepare,
                        onPressed: () async {
                          await openReminderSheet(context, p.id);
                          if (context.mounted) {
                            context.read<CollectionsBloc>().add(
                              const RefreshReport(),
                            );
                          }
                        },
                      ),
                      if (p != data.items.last) const Divider(),
                    ],
                  ],
                ),
        ),
      ],
    );
  }
}
