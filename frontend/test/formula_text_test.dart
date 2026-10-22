import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shgad/core/widgets/formula_text.dart';
import 'package:shgad/l10n/generated/app_localizations.dart';

void main() {
  for (final locale in ['ar', 'en']) {
    test('Formula explanations retain exact meaning in $locale', () async {
      final l = await AppLocalizations.delegate.load(Locale(locale));
      expect(
        formulaText(l, 'cash_on_hand - supplier_dues'),
        l.formulaConfirmed,
      );
      expect(
        formulaText(l, 'original amount - active verified allocations'),
        l.formulaDebt,
      );
      expect(
        formulaText(
          l,
          'sum active recorded CREDIT_COLLECTION in resolved range',
        ),
        l.formulaRecorded(l.collection),
      );
      expect(
        formulaText(
          l,
          'FINANCIAL_RULES §6: sum projected cash_sales inflows over 30 days',
        ),
        l.formulaProjected(l.recordedSalesDriver),
      );
      // These real backend formulas mean different things despite shared words.
      for (final raw in [
        'payment amount - active verified allocations',
        'sum eligible outstanding; overdue receivables excluded from expected',
        'sum eligible outstanding at cutoff',
        'cutoff cash first; previous projected closing thereafter',
        'minimum projected closing across 30 days',
        'length of fixed 30-day projected series',
        'FINANCIAL_RULES §6: base projected cash_sales from cutoff-visible history/schedule',
        'CASH_SALE - OWNER_DRAWING',
        'future unrecognized allocations formula',
      ]) {
        expect(formulaText(l, raw), l.formulaUnavailable, reason: raw);
      }
    });
  }
}
