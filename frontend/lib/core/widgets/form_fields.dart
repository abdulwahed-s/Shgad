import 'package:flutter/services.dart';
import 'package:flutter/material.dart';
import '../../l10n/generated/app_localizations.dart';
import '../constants/app_dimens.dart';
import '../utils/iqd_formatter.dart';
import '../utils/digit_normalizer.dart';
import '../theme/app_theme.dart';
import '../theme/app_motion.dart';
import 'focus_outline.dart';
import 'ledger_widgets.dart' show DisabledChip;

Widget ledgerTextField(
  BuildContext context, {
  Key? key,
  TextEditingController? controller,
  String? initialValue,
  bool enabled = true,
  bool readOnly = false,
  TextInputType? keyboardType,
  required InputDecoration decoration,
  ValueChanged<String>? onChanged,
}) => FieldLabel(
  label: decoration.labelText ?? '',
  child: TextFormField(
    key: key,
    controller: controller,
    initialValue: initialValue,
    enabled: enabled,
    readOnly: readOnly,
    keyboardType: keyboardType,
    style: Theme.of(context).extension<LedgerStyles>()!.input(enabled: enabled),
    decoration: decoration.copyWith(
      labelText: '',
      floatingLabelBehavior: FloatingLabelBehavior.never,
    ),
    onChanged: onChanged,
  ),
);

Widget ledgerDropdown<T>(
  BuildContext context, {
  Key? key,
  T? initialValue,
  bool isExpanded = true,
  required InputDecoration decoration,
  required List<DropdownMenuItem<T>> items,
  ValueChanged<T?>? onChanged,
}) => FieldLabel(
  label: decoration.labelText ?? '',
  child: DropdownMenuFormField<T>(
    key: key,
    initialSelection: initialValue,
    enabled: onChanged != null,
    selectOnly: true,
    expandedInsets: EdgeInsets.zero,
    maxLines: 1,
    textStyle: Theme.of(
      context,
    ).extension<LedgerStyles>()!.input(enabled: onChanged != null),
    decorationBuilder: (_, controller) => decoration.copyWith(
      labelText: '',
      floatingLabelBehavior: FloatingLabelBehavior.never,
    ),
    dropdownMenuEntries: [
      for (final item in items)
        DropdownMenuEntry<T>(
          value: item.value as T,
          label: (item.child as Text).data!,
          labelWidget: item.child,
          enabled: item.enabled,
        ),
    ],
    onSelected: onChanged,
  ),
);

class FieldLabel extends StatelessWidget {
  const FieldLabel({
    required this.label,
    required this.child,
    this.group = false,
    super.key,
  });
  final String label;
  final Widget child;
  final bool group;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppDimens.lg),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ExcludeSemantics(
          child: Text(label, style: Theme.of(context).textTheme.labelMedium),
        ),
        const SizedBox(height: AppDimens.xs),
        if (group)
          Semantics(
            container: true,
            explicitChildNodes: true,
            label: label,
            child: child,
          )
        else
          FocusOutline(
            child: MergeSemantics(
              child: Semantics(label: label, child: child),
            ),
          ),
      ],
    ),
  );
}

class DateField extends StatefulWidget {
  const DateField({
    required this.label,
    required this.value,
    required this.onChanged,
    this.enabled = true,
    this.locked = false,
    this.fieldKey,
    this.businessDate,
    super.key,
  });
  final String label, value;
  final String? businessDate;
  final ValueChanged<String> onChanged;
  final bool enabled, locked;
  final Key? fieldKey;
  @override
  State<DateField> createState() => _DateFieldState();
}

class _DateFieldState extends State<DateField> {
  final controller = TextEditingController();
  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    controller.text = IqdFormatter.digits(widget.value, l.localeName);
    return FieldLabel(
      label: widget.label,
      child: TextFormField(
        key: widget.fieldKey,
        controller: controller,
        readOnly: true,
        textDirection: TextDirection.ltr,
        textAlign: TextAlign.end,
        enabled: widget.enabled,
        style: Theme.of(
          context,
        ).extension<LedgerStyles>()!.input(enabled: widget.enabled),
        decoration: const InputDecoration(),
        onTap: widget.locked
            ? null
            : () async {
                final date =
                    DateTime.tryParse(widget.value) ??
                    DateTime.tryParse(widget.businessDate ?? '');
                if (date == null) {
                  return;
                }
                final selected = await showDialog<DateTime>(
                  context: context,
                  animationStyle: AnimationStyle(
                    duration: AppMotion.route(context),
                    reverseDuration: AppMotion.route(context),
                  ),
                  builder: (context) => DatePickerDialog(
                    initialDate: date,
                    currentDate:
                        DateTime.tryParse(
                          widget.businessDate ?? widget.value,
                        ) ??
                        date,
                    initialEntryMode: DatePickerEntryMode.inputOnly,
                    calendarDelegate: l.localeName == 'ar'
                        ? const _ArabicCalendarDelegate()
                        : const GregorianCalendarDelegate(),
                    firstDate: DateTime(2000),
                    lastDate: DateTime(2100),
                  ),
                );
                if (selected != null) {
                  widget.onChanged(
                    '${selected.year.toString().padLeft(4, '0')}-${selected.month.toString().padLeft(2, '0')}-${selected.day.toString().padLeft(2, '0')}',
                  );
                }
              },
      ),
    );
  }
}

/// Retains Material's Gregorian parsing/calendar and localized month names.
/// Only the displayed digits change; both supported digit sets remain valid.
class _ArabicCalendarDelegate extends GregorianCalendarDelegate {
  const _ArabicCalendarDelegate();

  @override
  String dateHelpText(MaterialLocalizations localizations) => '';

  @override
  String formatCompactDate(
    DateTime date,
    MaterialLocalizations localizations,
  ) => IqdFormatter.digits(super.formatCompactDate(date, localizations), 'ar');

  @override
  String formatMediumDate(DateTime date, MaterialLocalizations localizations) =>
      IqdFormatter.digits(super.formatMediumDate(date, localizations), 'ar');

  @override
  DateTime? parseCompactDate(
    String? inputString,
    MaterialLocalizations localizations,
  ) {
    if (inputString == null) return null;
    final normalized = DigitNormalizer.normalize(inputString);
    final parsed = super.parseCompactDate(normalized, localizations);
    if (parsed != null) return parsed;
    // Material's Arabic format includes directional marks before separators.
    // User input does not need those invisible marks to be a valid date.
    final marked = normalized
        .replaceAll(RegExp(r'[\u200e\u200f\u061c]'), '')
        .replaceAll('/', '\u200f/');
    return super.parseCompactDate(marked, localizations);
  }
}

class AmountField extends StatelessWidget {
  const AmountField({
    required this.controller,
    required this.onChanged,
    this.enabled = true,
    this.fieldKey,
    this.label,
    super.key,
  });
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  final bool enabled;
  final Key? fieldKey;
  final String? label;
  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final digits = IqdFormatter.digits(controller.text, l.localeName);
    if (digits != controller.text) {
      controller.value = controller.value.copyWith(text: digits);
    }
    return FieldLabel(
      label: label ?? l.amountInput,
      child: TextFormField(
        key: fieldKey,
        controller: controller,
        enabled: enabled,
        keyboardType: TextInputType.number,
        inputFormatters: [
          TextInputFormatter.withFunction(
            (old, value) => value.copyWith(
              text: IqdFormatter.digits(value.text, l.localeName),
            ),
          ),
        ],
        style: Theme.of(
          context,
        ).extension<LedgerStyles>()!.input(enabled: enabled, amount: true),
        decoration: InputDecoration(
          suffix: Text(
            l.iqd,
            style: enabled
                ? Theme.of(context).textTheme.bodySmall
                : Theme.of(context).extension<LedgerStyles>()!.captionOnSoft,
          ),
        ),
        onChanged: onChanged,
      ),
    );
  }
}

class ChoiceChips extends StatelessWidget {
  const ChoiceChips({
    required this.choices,
    required this.selected,
    required this.onSelected,
    super.key,
  });
  final Map<String, String> choices;
  final String selected;
  final ValueChanged<String>? onSelected;
  @override
  Widget build(BuildContext context) => Wrap(
    spacing: AppDimens.sm,
    runSpacing: AppDimens.sm,
    children: [
      for (final item in choices.entries)
        FocusOutline(
          enabled: onSelected != null,
          child: onSelected == null
              ? DisabledChip(text: item.value, selected: item.key == selected)
              : ChoiceChip(
                  chipAnimationStyle: AppMotion.chip(context),
                  label: Text(item.value),
                  labelStyle: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: onSelected == null
                        ? Theme.of(context).disabledColor
                        : item.key == selected
                        ? Theme.of(context).colorScheme.primary
                        : Theme.of(context).colorScheme.onSurface,
                  ),
                  checkmarkColor: onSelected == null
                      ? Theme.of(context).disabledColor
                      : Theme.of(context).colorScheme.primary,
                  color: Theme.of(context).chipTheme.color,
                  selected: item.key == selected,
                  onSelected: onSelected == null
                      ? null
                      : (_) => onSelected!(item.key),
                ),
        ),
    ],
  );
}

class SegmentedControl extends StatelessWidget {
  const SegmentedControl({
    required this.choices,
    required this.selected,
    required this.onSelected,
    super.key,
  });
  final Map<String, String> choices;
  final String selected;
  final ValueChanged<String>? onSelected;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, bounds) {
      double widest = 0;
      for (final label in choices.values) {
        final painter = TextPainter(
          text: TextSpan(
            text: label,
            style: Theme.of(context).textTheme.labelMedium,
          ),
          textDirection: Directionality.of(context),
          textScaler: MediaQuery.textScalerOf(context),
        )..layout();
        if (painter.width > widest) {
          widest = painter.width;
        }
      }
      final vertical =
          (widest + AppDimens.iconSize + AppDimens.sm * 3) * choices.length >
          bounds.maxWidth;
      return FocusOutline(
        child: SizedBox(
          height: vertical
              ? MediaQuery.textScalerOf(context).scale(AppDimens.minTarget) *
                    choices.length
              : null,
          child: SegmentedButton<String>(
            direction: vertical ? Axis.vertical : Axis.horizontal,
            expandedInsets: EdgeInsets.zero,
            segments: [
              for (final item in choices.entries)
                ButtonSegment(
                  value: item.key,
                  label: Text(item.value, maxLines: 1, softWrap: false),
                ),
            ],
            selected: {selected},
            onSelectionChanged: onSelected == null
                ? null
                : (v) => onSelected!(v.single),
          ),
        ),
      );
    },
  );
}
