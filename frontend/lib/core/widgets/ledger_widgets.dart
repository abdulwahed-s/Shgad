import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../domain/amount.dart';
import '../utils/iqd_formatter.dart';
import '../utils/date_formatter.dart';

class LedgerCard extends StatelessWidget {
  const LedgerCard({required this.child, super.key});
  final Widget child;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(AppDimens.lg),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      border: Border.all(color: Theme.of(context).colorScheme.outline),
      borderRadius: BorderRadius.circular(AppDimens.radiusMd),
    ),
    child: child,
  );
}

class StatusLabel extends StatelessWidget {
  const StatusLabel({required this.kind, super.key});
  final String kind;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final c = Theme.of(context).colorScheme;
    final (text, background, foreground) = switch (kind) {
      'expected' => (l.expected, c.tertiaryContainer, c.onTertiaryContainer),
      'missing' => (l.missing, c.surfaceContainerHighest, c.onSurfaceVariant),
      'flagged' => (l.flagged, c.errorContainer, c.onErrorContainer),
      'calculated' => (l.calculated, c.tertiary, c.onTertiary),
      'entered' => (l.entered, c.surfaceContainerHighest, c.onSurfaceVariant),
      _ => (l.verified, c.tertiary, c.onTertiary),
    };
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppDimens.sm,
        vertical: AppDimens.xs,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(AppDimens.radiusSm),
      ),
      child: Text(
        text,
        style: Theme.of(
          context,
        ).textTheme.labelLarge?.copyWith(color: foreground),
      ),
    );
  }
}

class AmountView extends StatelessWidget {
  const AmountView({
    required this.amount,
    required this.label,
    this.hero = false,
    this.exact = false,
    this.onTap,
    this.caption,
    super.key,
  });
  final Amount amount;
  final String label;
  final bool hero;
  final bool exact;
  final VoidCallback? onTap;
  final String? caption;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Semantics(
      button: onTap != null,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AppDimens.sm),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.bodyLarge),
              Text(
                amount.value == null
                    ? l.missing
                    : IqdFormatter.format(
                        amount.value!,
                        l.localeName,
                        l.thousand,
                        l.iqd,
                        exact: exact,
                      ),
                style:
                    (hero
                            ? Theme.of(context).textTheme.headlineLarge
                            : Theme.of(context).textTheme.titleSmall)
                        ?.copyWith(
                          decoration: onTap == null
                              ? null
                              : TextDecoration.underline,
                          decorationStyle: TextDecorationStyle.dotted,
                        ),
              ),
              const SizedBox(height: AppDimens.xs),
              StatusLabel(kind: amount.kind),
              if (caption != null)
                Text(caption!, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    );
  }
}

class InfoStrip extends StatelessWidget {
  const InfoStrip({required this.text, this.expected = false, super.key});
  final String text;
  final bool expected;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(AppDimens.md),
    decoration: BoxDecoration(
      color: expected
          ? Theme.of(context).colorScheme.tertiaryContainer
          : Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(AppDimens.sm),
    ),
    child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
  );
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({required this.text, required this.onPressed, super.key});
  final String text;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) =>
      FilledButton(onPressed: onPressed, child: Text(text));
}

class SecondaryButton extends StatelessWidget {
  const SecondaryButton({
    required this.text,
    required this.onPressed,
    super.key,
  });
  final String text;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) =>
      OutlinedButton(onPressed: onPressed, child: Text(text));
}

class PromptChip extends StatelessWidget {
  const PromptChip({required this.text, required this.onPressed, super.key});
  final String text;
  final VoidCallback onPressed;
  @override
  Widget build(BuildContext context) => ActionChip(
    label: Text(text),
    onPressed: onPressed,
    backgroundColor: Theme.of(context).colorScheme.surface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppDimens.radiusSm),
      side: BorderSide(color: Theme.of(context).colorScheme.outline),
    ),
  );
}

class OfflineBanner extends StatelessWidget {
  const OfflineBanner({required this.updatedAt, super.key});
  final String updatedAt;
  @override
  Widget build(BuildContext context) => InfoStrip(
    text: AppLocalizations.of(context).offlineUpdated(
      AppLocalizations.of(context).timeInBaghdad(
        formatDate(
          updatedAt,
          AppLocalizations.of(context).localeName,
          timestamp: true,
        ),
      ),
    ),
  );
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.text,
    required this.action,
    required this.onPressed,
    super.key,
  });
  final String text;
  final String action;
  final VoidCallback onPressed;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(text),
      SecondaryButton(text: action, onPressed: onPressed),
    ],
  );
}

class NumberBadge extends StatelessWidget {
  const NumberBadge({required this.number, super.key});
  final int number;
  @override
  Widget build(BuildContext context) => Container(
    width: 32,
    height: 32,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      border: Border.all(color: Theme.of(context).colorScheme.outline),
    ),
    child: Text(
      IqdFormatter.digits(
        number.toString().padLeft(2, '0'),
        AppLocalizations.of(context).localeName,
      ),
      style: Theme.of(context).textTheme.labelLarge,
    ),
  );
}

class EvidenceSheet extends StatelessWidget {
  const EvidenceSheet({
    required this.formula,
    required this.children,
    super.key,
  });
  final String formula;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.all(AppDimens.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(formula, style: Theme.of(context).textTheme.titleMedium),
          ...children,
        ],
      ),
    ),
  );
}
