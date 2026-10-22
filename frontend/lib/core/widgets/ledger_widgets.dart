import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../domain/amount.dart';
import '../theme/app_theme.dart';
import '../theme/app_motion.dart';
import '../utils/iqd_formatter.dart';
import '../utils/date_formatter.dart';
import 'section_label.dart';
import 'focus_outline.dart';
import 'formula_text.dart';
import 'balanced_text.dart';

String statusText(AppLocalizations l, String kind) => switch (kind) {
  'expected' => l.expected,
  'missing' => l.missing,
  'flagged' => l.flagged,
  'calculated' => l.calculated,
  'entered' => l.entered,
  _ => l.verified,
};

class LedgerCard extends StatelessWidget {
  const LedgerCard({
    required this.child,
    this.padding = AppDimens.lg,
    super.key,
  });
  final Widget child;
  final double padding;
  @override
  Widget build(BuildContext context) => Material(
    color: Theme.of(context).colorScheme.surface,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppDimens.radiusMd),
      side: BorderSide(color: Theme.of(context).colorScheme.outline),
    ),
    child: Padding(padding: EdgeInsets.all(padding), child: child),
  );
}

class HeroCard extends StatelessWidget {
  const HeroCard({
    this.amount,
    this.label,
    this.sentence,
    this.caption,
    this.kind = 'expected',
    this.onTap,
    super.key,
  });
  final Amount? amount;
  final String? label, sentence, caption;
  final String? kind;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => LedgerCard(
    padding: AppDimens.heroPadding,
    child: amount != null
        ? AmountView(
            amount: amount!,
            label: label!,
            hero: true,
            caption: caption,
            onTap: onTap,
          )
        : Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (label != null)
                Text(
                  label!,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              const SizedBox(height: AppDimens.xs),
              BalancedText(
                sentence!,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              if (kind != null) ...[
                const SizedBox(height: AppDimens.md),
                StatusPill(kind: kind!),
              ],
              if (caption != null)
                Padding(
                  padding: const EdgeInsets.only(top: AppDimens.sm),
                  child: Text(
                    caption!,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
            ],
          ),
  );
}

class StatusPill extends StatelessWidget {
  const StatusPill({required this.kind, this.text, super.key});
  final String kind;
  final String? text;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final c = Theme.of(context).colorScheme;
    final (background, foreground) = switch (kind) {
      'expected' => (c.tertiaryContainer, c.onTertiaryContainer),
      'missing' || 'entered' => (c.surfaceContainerHighest, c.onSurfaceVariant),
      'flagged' => (c.errorContainer, c.onErrorContainer),
      _ => (c.tertiary, c.onTertiary),
    };
    return Align(
      alignment: AlignmentDirectional.centerStart,
      widthFactor: 1,
      heightFactor: 1,
      child: Container(
        constraints: const BoxConstraints(minHeight: AppDimens.pillHeight),
        padding: const EdgeInsets.symmetric(
          horizontal: AppDimens.sm,
          vertical: AppDimens.xs,
        ),
        decoration: BoxDecoration(
          color: background,
          borderRadius: BorderRadius.circular(AppDimens.radiusSm),
        ),
        child: Text(
          text ?? statusText(l, kind),
          style: Theme.of(
            context,
          ).textTheme.labelSmall?.copyWith(color: foreground),
        ),
      ),
    );
  }
}

class StatusLabel extends StatusPill {
  const StatusLabel({required super.kind, super.key});
}

/// Formatting only: both spans come from the single exact IQD formatter.
class AmountValue extends StatelessWidget {
  const AmountValue({
    required this.text,
    this.hero = false,
    this.small = false,
    this.voided = false,
    this.link = false,
    super.key,
  });
  final String text;
  final bool hero, small, voided, link;
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Keep localized multi-word units together (for example, thousand IQD).
    final split = text.indexOf(' ');
    final number = split < 0 ? text : text.substring(0, split);
    final unit = split < 0 ? '' : text.substring(split + 1);
    final style = (hero
        ? theme.textTheme.headlineLarge
        : small
        ? theme.extension<LedgerStyles>()!.amountSmall
        : theme.textTheme.titleSmall)!;
    final decorated = style.copyWith(
      decoration: voided
          ? TextDecoration.lineThrough
          : link
          ? TextDecoration.underline
          : null,
      decorationStyle: TextDecorationStyle.dotted,
      decorationColor: theme.colorScheme.primary,
    );
    if (!hero) return Text(text, textAlign: TextAlign.end, style: decorated);
    final baseline = MediaQuery.textScalerOf(
      context,
    ).scale(AppDimens.heroFontSize);
    return Wrap(
      alignment: WrapAlignment.start,
      spacing: AppDimens.sm,
      runSpacing: AppDimens.xs,
      children: [
        Baseline(
          baseline: baseline,
          baselineType: TextBaseline.alphabetic,
          child: Text(
            number,
            softWrap: false,
            style: decorated,
            textDirection: TextDirection.ltr,
          ),
        ),
        if (unit.isNotEmpty)
          Baseline(
            baseline: baseline,
            baselineType: TextBaseline.alphabetic,
            child: Text(unit, style: theme.extension<LedgerStyles>()!.heroUnit),
          ),
      ],
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
    this.voided = false,
    this.secondary,
    this.table = false,
    this.interactive = false,
    super.key,
  });
  final Amount amount;
  final String label;
  final bool hero, exact, voided, table, interactive;
  final VoidCallback? onTap;
  final String? caption;
  final String? secondary;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final active = onTap != null || interactive;
    final value = amount.value == null
        ? l.missing
        : IqdFormatter.format(
            amount.value!,
            l.localeName,
            l.thousand,
            l.iqd,
            exact: exact,
          );
    final labelWidget = BalancedText(
      label,
      style: (hero ? theme.textTheme.bodyLarge : theme.textTheme.labelMedium)
          ?.copyWith(
            color: hero && !active
                ? theme.colorScheme.onSurfaceVariant
                : theme.colorScheme.onSurface,
          ),
    );
    final captionWidget = caption == null
        ? null
        : Text(
            caption!,
            style: !active
                ? theme.textTheme.bodySmall
                : theme.extension<LedgerStyles>()!.interactiveCaption,
          );
    final amountWidget = AmountValue(
      text: value,
      hero: hero,
      voided: voided,
      link: onTap != null,
    );
    Widget contents;
    if (hero) {
      contents = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          labelWidget,
          const SizedBox(height: AppDimens.xs),
          amountWidget,
          const SizedBox(height: AppDimens.sm),
          Wrap(
            spacing: AppDimens.sm,
            runSpacing: AppDimens.sm,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              StatusLabel(kind: voided ? 'flagged' : amount.kind),
              ?captionWidget,
            ],
          ),
        ],
      );
    } else if (table) {
      contents = Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisSize: MainAxisSize.min,
        children: [
          amountWidget,
          const SizedBox(height: AppDimens.xs),
          StatusLabel(kind: voided ? 'flagged' : amount.kind),
        ],
      );
    } else {
      contents = LayoutBuilder(
        builder: (context, bounds) {
          final p = TextPainter(
            text: TextSpan(text: value, style: theme.textTheme.titleSmall),
            textDirection: Directionality.of(context),
            textScaler: MediaQuery.textScalerOf(context),
          )..layout();
          double textWidth(String text, TextStyle? style) => (TextPainter(
            text: TextSpan(text: text, style: style),
            textDirection: Directionality.of(context),
            textScaler: MediaQuery.textScalerOf(context),
          )..layout()).width;
          final pillWidth =
              textWidth(
                statusText(l, voided ? 'flagged' : amount.kind),
                theme.textTheme.labelSmall,
              ) +
              AppDimens.sm * 2;
          var figuresWidth = p.width > pillWidth ? p.width : pillWidth;
          if (secondary != null) {
            final secondaryWidth = textWidth(
              secondary!,
              theme.extension<LedgerStyles>()!.amountSmall,
            );
            if (secondaryWidth > figuresWidth) figuresWidth = secondaryWidth;
          }
          figuresWidth = figuresWidth.clamp(0, bounds.maxWidth * .55);
          final labelStyle = theme.textTheme.labelMedium!;
          final labelPainter =
              TextPainter(
                text: TextSpan(text: label, style: labelStyle),
                textDirection: Directionality.of(context),
                textScaler: MediaQuery.textScalerOf(context),
                maxLines: 2,
              )..layout(
                maxWidth: (bounds.maxWidth - figuresWidth - AppDimens.lg).clamp(
                  1,
                  bounds.maxWidth,
                ),
              );
          final stack =
              p.width > bounds.maxWidth * .55 || labelPainter.didExceedMaxLines;
          final figures = Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              amountWidget,
              const SizedBox(height: AppDimens.xs),
              StatusLabel(kind: voided ? 'flagged' : amount.kind),
              if (secondary != null)
                Padding(
                  padding: const EdgeInsets.only(top: AppDimens.xs),
                  child: Text(
                    secondary!,
                    style: theme.extension<LedgerStyles>()!.amountSmall,
                    textAlign: TextAlign.end,
                  ),
                ),
            ],
          );
          final labels = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [labelWidget],
          );
          if (stack) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                labels,
                const SizedBox(height: AppDimens.sm),
                Align(
                  alignment: AlignmentDirectional.centerEnd,
                  child: figures,
                ),
                if (captionWidget != null) ...[
                  const SizedBox(height: AppDimens.sm),
                  captionWidget,
                ],
              ],
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: labels),
                  const SizedBox(width: AppDimens.lg),
                  ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: bounds.maxWidth * .55,
                    ),
                    child: figures,
                  ),
                ],
              ),
              if (captionWidget != null) ...[
                const SizedBox(height: AppDimens.sm),
                captionWidget,
              ],
            ],
          );
        },
      );
    }
    return Semantics(
      label: [
        label,
        value,
        statusText(l, voided ? 'flagged' : amount.kind),
        ?caption,
        ?secondary,
      ].join(', '),
      button: onTap != null,
      onTap: onTap,
      excludeSemantics: true,
      child: FocusOutline(
        enabled: onTap != null,
        child: InkWell(
          onTap: onTap,
          overlayColor: AppTheme.overlay,
          borderRadius: BorderRadius.circular(AppDimens.radiusSm),
          child: Ink(
            decoration: BoxDecoration(
              color: onTap == null
                  ? null
                  : AppTheme.overlay.resolve(InteractionPreview.of(context)),
              borderRadius: BorderRadius.circular(AppDimens.radiusSm),
            ),
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                minHeight: AppDimens.toolbarHeight,
              ),
              child: Padding(
                padding: EdgeInsets.symmetric(
                  vertical: hero ? 0 : AppDimens.md,
                ),
                child: contents,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class LedgerRow extends StatelessWidget {
  const LedgerRow({
    required this.amount,
    required this.label,
    this.onTap,
    this.caption,
    this.exact = false,
    this.voided = false,
    this.secondary,
    this.interactive = false,
    super.key,
  });
  final Amount amount;
  final String label;
  final VoidCallback? onTap;
  final String? caption;
  final bool exact, voided, interactive;
  final String? secondary;
  @override
  Widget build(BuildContext context) => AmountView(
    amount: amount,
    label: label,
    onTap: onTap,
    caption: caption,
    exact: exact,
    voided: voided,
    secondary: secondary,
    interactive: interactive,
  );
}

class LedgerGroup extends StatelessWidget {
  const LedgerGroup({
    required this.children,
    this.title,
    this.caption,
    super.key,
  });
  final List<Widget> children;
  final String? title, caption;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (title != null) SectionLabel(text: title!),
      if (caption != null)
        Padding(
          padding: const EdgeInsets.only(bottom: AppDimens.sm),
          child: Text(caption!, style: Theme.of(context).textTheme.bodySmall),
        ),
      LedgerCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < children.length; i++) ...[
              if (i > 0)
                const Padding(
                  padding: EdgeInsetsDirectional.only(start: AppDimens.lg),
                  child: Divider(),
                ),
              children[i],
            ],
          ],
        ),
      ),
    ],
  );
}

class InfoStrip extends StatelessWidget {
  const InfoStrip({
    required this.text,
    this.expected = false,
    this.error = false,
    this.offline = false,
    super.key,
  });
  final String text;
  final bool expected, error, offline;
  @override
  Widget build(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppDimens.lg,
        vertical: AppDimens.md,
      ),
      decoration: BoxDecoration(
        color: error
            ? c.errorContainer
            : expected
            ? c.tertiaryContainer
            : c.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppDimens.radiusMd),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (offline || error) ...[
            Icon(
              offline ? Icons.cloud_off_outlined : Icons.error_outline,
              color: error ? c.error : c.onSurfaceVariant,
              size: AppDimens.iconSize,
            ),
            const SizedBox(width: AppDimens.sm),
          ],
          Expanded(
            child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
          ),
        ],
      ),
    );
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    required this.text,
    required this.onPressed,
    this.compact = false,
    this.statesController,
    super.key,
  });
  final String text;
  final VoidCallback? onPressed;
  final bool compact;
  final WidgetStatesController? statesController;
  @override
  Widget build(BuildContext context) => FocusOutline(
    enabled: onPressed != null,
    child: FilledButton(
      statesController: statesController,
      onPressed: onPressed,
      child: Text(text, textAlign: TextAlign.center),
    ),
  );
}

class SecondaryButton extends StatelessWidget {
  const SecondaryButton({
    required this.text,
    required this.onPressed,
    this.statesController,
    super.key,
  });
  final String text;
  final VoidCallback? onPressed;
  final WidgetStatesController? statesController;
  @override
  Widget build(BuildContext context) => FocusOutline(
    enabled: onPressed != null,
    child: OutlinedButton(
      statesController: statesController,
      onPressed: onPressed,
      child: Text(text, textAlign: TextAlign.center),
    ),
  );
}

class TextAction extends StatelessWidget {
  const TextAction({required this.text, required this.onPressed, super.key});
  final String text;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) => FocusOutline(
    child: TextButton(onPressed: onPressed, child: Text(text)),
  );
}

class ActionGroup extends StatelessWidget {
  const ActionGroup({required this.children, super.key});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, bounds) {
      double needed = AppDimens.md * (children.length - 1);
      for (final child in children) {
        final text = switch (child) {
          PrimaryButton(:final text) ||
          SecondaryButton(:final text) ||
          TextAction(:final text) => text,
          _ => null,
        };
        if (text == null) {
          needed += bounds.maxWidth;
          continue;
        }
        final painter = TextPainter(
          text: TextSpan(
            text: text,
            style: Theme.of(context).textTheme.labelMedium,
          ),
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
        )..layout();
        needed += painter.width + AppDimens.lg * 2;
      }
      final stacked = needed > bounds.maxWidth;
      return OverflowBar(
        spacing: AppDimens.md,
        overflowSpacing: AppDimens.md,
        alignment: MainAxisAlignment.start,
        overflowAlignment: OverflowBarAlignment.start,
        children: [
          for (final child in children)
            ConstrainedBox(
              constraints: BoxConstraints(
                minWidth: stacked ? bounds.maxWidth : 0,
                maxWidth: bounds.maxWidth,
              ),
              child: child,
            ),
        ],
      );
    },
  );
}

class PromptChip extends StatelessWidget {
  const PromptChip({required this.text, required this.onPressed, super.key});
  final String text;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) => FocusOutline(
    enabled: onPressed != null,
    child: onPressed == null
        ? DisabledChip(text: text)
        : ActionChip(
            chipAnimationStyle: AppMotion.chip(context),
            label: Text(text),
            onPressed: onPressed,
            labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: onPressed == null
                  ? Theme.of(context).disabledColor
                  : Theme.of(context).colorScheme.onSurface,
            ),
            color: Theme.of(context).chipTheme.color,
          ),
  );
}

/// RawChip's built-in disabled render layer fades labels regardless of theme.
/// A non-interactive Chip preserves the required opaque disabled palette.
class DisabledChip extends StatelessWidget {
  const DisabledChip({required this.text, this.selected = false, super.key});
  final String text;
  final bool selected;
  @override
  Widget build(BuildContext context) => Semantics(
    label: text,
    button: true,
    enabled: false,
    checked: selected,
    excludeSemantics: true,
    child: ExcludeFocus(
      child: Chip(
        label: Text(text),
        avatar: selected
            ? Icon(Icons.check, color: Theme.of(context).disabledColor)
            : null,
        labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
          color: Theme.of(context).disabledColor,
        ),
        color: WidgetStatePropertyAll(
          Theme.of(context).colorScheme.surfaceContainerHighest,
        ),
      ),
    ),
  );
}

class OfflineBanner extends StatelessWidget {
  const OfflineBanner({required this.updatedAt, super.key});
  final String updatedAt;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return InfoStrip(
      offline: true,
      text: l.offlineUpdated(
        l.timeInBaghdad(formatDate(updatedAt, l.localeName, timestamp: true)),
      ),
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    required this.text,
    required this.action,
    required this.onPressed,
    this.explanation,
    super.key,
  });
  final String text, action;
  final String? explanation;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: AppDimens.xxxl),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(text, style: Theme.of(context).textTheme.titleMedium),
        if (explanation != null) ...[
          const SizedBox(height: AppDimens.sm),
          Text(explanation!),
        ],
        const SizedBox(height: AppDimens.xl),
        SecondaryButton(text: action, onPressed: onPressed),
      ],
    ),
  );
}

class InlineProgress extends StatelessWidget {
  const InlineProgress({super.key});
  @override
  Widget build(BuildContext context) =>
      const LinearProgressIndicator(minHeight: AppDimens.progressHeight);
}

class NumberBadge extends StatelessWidget {
  const NumberBadge({required this.number, super.key});
  final int number;
  @override
  Widget build(BuildContext context) => Container(
    width: MediaQuery.textScalerOf(context).scale(AppDimens.numberBadgeSize),
    height: MediaQuery.textScalerOf(context).scale(AppDimens.numberBadgeSize),
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
      style: Theme.of(context).extension<LedgerStyles>()!.section,
    ),
  );
}

/// A selectable source caption with a full-sized accessibility/selection region.
class SelectableCaption extends StatelessWidget {
  const SelectableCaption(this.text, {this.style, super.key});
  final String text;
  final TextStyle? style;
  @override
  Widget build(BuildContext context) => MergeSemantics(
    child: ConstrainedBox(
      constraints: const BoxConstraints(minHeight: AppDimens.minTarget),
      child: SelectableText(
        text,
        semanticsLabel: text,
        style: style ?? Theme.of(context).textTheme.bodySmall,
      ),
    ),
  );
}

class EvidenceSheet extends StatelessWidget {
  const EvidenceSheet({
    required this.formula,
    required this.children,
    this.showHeader = false,
    this.onClose,
    this.controller,
    this.closeEnabled = true,
    super.key,
  });
  final String formula;
  final List<Widget> children;
  final bool showHeader;
  final VoidCallback? onClose;
  final ScrollController? controller;
  final bool closeEnabled;
  @override
  Widget build(BuildContext context) => SafeArea(
    child: SingleChildScrollView(
      controller: controller,
      padding: const EdgeInsets.all(AppDimens.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (showHeader) ...[
            Center(
              child: Container(
                width: AppDimens.xxl,
                height: AppDimens.xs,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.outlineVariant,
                  borderRadius: BorderRadius.circular(AppDimens.radiusSm),
                ),
              ),
            ),
            const SizedBox(height: AppDimens.sm),
            Row(
              children: [
                Expanded(
                  child: Text(
                    AppLocalizations.of(context).evidence,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                IconButton(
                  tooltip: AppLocalizations.of(context).dismiss,
                  onPressed: closeEnabled
                      ? onClose ?? () => Navigator.of(context).maybePop()
                      : null,
                  icon: const Icon(Icons.close_outlined),
                ),
              ],
            ),
            const SizedBox(height: AppDimens.lg),
          ],
          if (formula.isNotEmpty) ...[
            InfoStrip(text: formulaText(AppLocalizations.of(context), formula)),
            if (formula != formulaText(AppLocalizations.of(context), formula))
              ExpansionTile(
                title: Text(
                  AppLocalizations.of(context).originalFormula,
                  style: Theme.of(
                    context,
                  ).extension<LedgerStyles>()!.interactiveCaption,
                ),
                children: [
                  SelectableCaption(
                    formula,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            const SizedBox(height: AppDimens.lg),
          ],
          ...children,
        ],
      ),
    ),
  );
}
