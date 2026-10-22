import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import '../../../../app/di/injection.dart';
import '../../../../core/constants/app_dimens.dart';
import '../../../../core/theme/app_motion.dart';
import '../../../../core/utils/date_formatter.dart';
import '../../../../core/widgets/failure_view.dart';
import '../../../../core/widgets/ledger_widgets.dart';
import '../../../../core/widgets/merchant_page.dart';
import '../../../../core/widgets/page_header.dart';
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
  Widget build(BuildContext context) => BlocListener<SampleBloc, SampleState>(
    listenWhen: (a, b) => !a.view.confirm && b.view.confirm,
    listener: (context, state) async {
      final bloc = context.read<SampleBloc>();
      final l = AppLocalizations.of(context);
      await showDialog<void>(
        context: context,
        animationStyle: AnimationStyle(
          duration: AppMotion.route(context),
          reverseDuration: AppMotion.route(context),
        ),
        builder: (_) => BlocProvider.value(
          value: bloc,
          child: BlocListener<SampleBloc, SampleState>(
            listenWhen: (a, b) => !b.view.confirm,
            listener: (context, state) => Navigator.of(context).pop(),
            child: BlocBuilder<SampleBloc, SampleState>(
              builder: (context, state) => AlertDialog(
                scrollable: true,
                title: Text(l.restoreSample),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(l.resetWarning),
                    if (state is SampleLoading)
                      const Padding(
                        padding: EdgeInsets.only(top: AppDimens.lg),
                        child: InlineProgress(),
                      ),
                    if (!state.view.online) ...[
                      const SizedBox(height: AppDimens.lg),
                      InfoStrip(text: l.needsConnection, offline: true),
                      TextAction(
                        text: l.retry,
                        onPressed: () => bloc.add(const RecheckSample()),
                      ),
                    ],
                    if (state is SampleFailure) ...[
                      const SizedBox(height: AppDimens.lg),
                      InfoStrip(
                        text: failureText(l, state.failure),
                        error: true,
                      ),
                    ],
                  ],
                ),
                actions: [
                  TextAction(
                    text: l.cancel,
                    onPressed: state is SampleLoading
                        ? null
                        : () => bloc.add(const CancelSampleReset()),
                  ),
                  PrimaryButton(
                    key: const ValueKey('sample_confirm'),
                    text: l.confirmReset,
                    onPressed: !state.view.online || state is SampleLoading
                        ? null
                        : () => bloc.add(const ConfirmSampleReset()),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
      if (!bloc.isClosed && bloc.state.view.confirm) {
        bloc.add(const CancelSampleReset());
      }
    },
    child: BlocBuilder<SampleBloc, SampleState>(
      builder: (context, state) {
        final l = AppLocalizations.of(context);
        final v = state.view;
        final bloc = context.read<SampleBloc>();
        final busy = state is SampleLoading;
        return MerchantPage(
          title: l.sampleTitle,
          children: [
            if (v.shop != null)
              PageMeta(
                date: l.businessDate(formatDate(v.shop!.date, l.localeName)),
              ),
            HeroCard(
              label: l.demoShopName,
              sentence: l.fictionalShop,
              kind: null,
            ),
            const SizedBox(height: AppDimens.xl),
            if (busy) const InlineProgress(),
            if (!v.online) ...[
              InfoStrip(text: l.needsConnection, offline: true),
              TextAction(
                text: l.retry,
                onPressed: () => bloc.add(const RecheckSample()),
              ),
            ],
            if (state is SampleFailure)
              InfoStrip(text: failureText(l, state.failure), error: true),
            if (v.saved) ...[
              InfoStrip(text: l.sampleReady),
              const SizedBox(height: AppDimens.lg),
              PrimaryButton(
                text: l.openToday,
                onPressed: () => context.go('/'),
              ),
              TextAction(
                text: l.chatTitle,
                onPressed: () => context.go('/chat'),
              ),
            ] else ...[
              PrimaryButton(
                key: const ValueKey('sample_prepare'),
                text: l.useSampleShort,
                onPressed: !v.online || busy || v.confirm
                    ? null
                    : () => bloc.add(const PrepareSampleReset()),
              ),
              const SizedBox(height: AppDimens.md),
              SecondaryButton(
                text: l.restoreSample,
                onPressed: !v.online || busy || v.confirm
                    ? null
                    : () => bloc.add(const PrepareSampleReset()),
              ),
            ],
            if (v.shop != null && !v.shop!.llmAvailable) ...[
              const SizedBox(height: AppDimens.lg),
              InfoStrip(text: l.chatNotConfigured),
            ],
          ],
        );
      },
    ),
  );
}
