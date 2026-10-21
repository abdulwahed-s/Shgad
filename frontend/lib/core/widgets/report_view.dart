import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../l10n/generated/app_localizations.dart';
import '../domain/snapshot.dart';
import '../presentation/report_bloc.dart';
import '../utils/date_formatter.dart';
import 'failure_view.dart';
import 'ledger_widgets.dart';

class ReportView<T, B extends ReportBloc<T>> extends StatelessWidget {
  const ReportView({required this.builder, super.key});
  final Widget Function(BuildContext, T) builder;
  @override
  Widget build(BuildContext context) => BlocBuilder<B, ReportState<T>>(
    builder: (context, state) {
      final Snapshot<T>? snapshot = switch (state) {
        ReportLoaded<T>(:final snapshot) ||
        ReportOffline<T>(:final snapshot) => snapshot,
        ReportLoading<T>(:final previous) => previous,
        _ => null,
      };
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (state is ReportInitial<T> || state is ReportLoading<T>)
            const LinearProgressIndicator(),
          if (state is ReportFailure<T>)
            FailureView(
              failure: state.failure,
              onRetry: () => context.read<B>().add(const RefreshReport()),
            ),
          if (snapshot != null) ...[
            if (snapshot.offline)
              OfflineBanner(updatedAt: snapshot.updatedAt)
            else
              Text(
                AppLocalizations.of(context).updatedAt(
                  AppLocalizations.of(context).timeInBaghdad(
                    formatDate(
                      snapshot.updatedAt,
                      AppLocalizations.of(context).localeName,
                      timestamp: true,
                    ),
                  ),
                ),
                style: Theme.of(context).textTheme.bodySmall,
              ),
            builder(context, snapshot.data),
          ],
        ],
      );
    },
  );
}
