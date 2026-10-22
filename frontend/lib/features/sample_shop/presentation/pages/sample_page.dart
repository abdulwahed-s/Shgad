import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../l10n/generated/app_localizations.dart';
import '../bloc/sample_bloc.dart';

class SamplePage extends StatelessWidget {
  const SamplePage({super.key});
  @override
  Widget build(BuildContext context) => BlocProvider(
    create: (_) => getIt<SampleBloc>()..add(const OpenSample()),
    child: const _SampleView(),
  );
}

class _SampleView extends StatelessWidget {
  const _SampleView();
  @override
  Widget build(BuildContext context) => BlocBuilder<SampleBloc, SampleState>(
    builder: (context, state) {
      final l = AppLocalizations.of(context);
      final v = state.view;
      final bloc = context.read<SampleBloc>();
      final busy = state is SampleLoading;
      return MerchantPage(
        title: l.sampleTitle,
        children: [
          Text(l.demoShopName, style: Theme.of(context).textTheme.titleLarge),
          if (!v.confirm) InfoStrip(text: l.fictionalShop),
          if (busy) const LinearProgressIndicator(),
          if (!v.online) ...[
            InfoStrip(text: l.needsConnection),
            SecondaryButton(
              text: l.retry,
              onPressed: () => bloc.add(const RecheckSample()),
            ),
          ],
          if (state is SampleFailure)
            InfoStrip(text: failureText(l, state.failure)),
          const SizedBox(height: AppDimens.xl),
          if (v.saved) ...[
            InfoStrip(text: l.sampleReady),
            PrimaryButton(text: l.openToday, onPressed: () => context.go('/')),
            SecondaryButton(
              text: l.chatTitle,
              onPressed: () => context.go('/chat'),
            ),
          ] else if (v.confirm) ...[
            InfoStrip(text: l.resetWarning),
            PrimaryButton(
              key: const ValueKey('sample_confirm'),
              text: l.confirmReset,
              onPressed: !v.online || busy
                  ? null
                  : () => bloc.add(const ConfirmSampleReset()),
            ),
            SecondaryButton(
              text: l.cancel,
              onPressed: busy
                  ? null
                  : () => bloc.add(const CancelSampleReset()),
            ),
          ] else
            PrimaryButton(
              key: const ValueKey('sample_prepare'),
              text: l.useSample,
              onPressed: !v.online || busy
                  ? null
                  : () => bloc.add(const PrepareSampleReset()),
            ),
          if (v.shop != null) ...[
            Text(l.businessDate(formatDate(v.shop!.date, l.localeName))),
            if (!v.shop!.llmAvailable) InfoStrip(text: l.chatNotConfigured),
          ],
        ],
      );
    },
  );
}
