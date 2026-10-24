# Synthetic forecast evaluation receipt

Split: `test`. Actual execution: 2026-10-23T19:36:13.770072+00:00 to 2026-10-23T19:36:16.847121+00:00.
Code commit: `4e13092d997d78f4e738ac0f368cfabb7123af3b`. Frozen method commit: `1dc2179ab1fe80ba799b11c518f1838fb10a523d`.
Dataset SHA-256: `fb9698b2ec22aafc9568ea804aba22dff3a2e6ac439de1b39fa366c5043b3ee6`. Model: `deterministic-no-llm`.
No provider request. Synthetic forecasting, no merchant validation.

| Shop | Cutoff | Predicted days per series | Scored days per series |
|---|---:|---:|---:|
| primary | 90 | 30 | 30 |
| SHOP-01 | 90 | 30 | 30 |
| SHOP-02 | 90 | 30 | 30 |
| SHOP-03 | 90 | 30 | 30 |

Scored-day-weighted metrics, baseline comparison, first-shortfall ±2 days and false-OK numerator/realized-short denominator/rate:

```json
{
  "base": {
    "absolute_error_sum_iqd": 117479402,
    "baseline_comparable_days": 120,
    "baseline_mae_iqd": 666064,
    "false_ok": {
      "available_cases": 4,
      "denominator": 0,
      "eligible_invoices": 4,
      "numerator": 0,
      "rate": null,
      "unavailable_cases": 0
    },
    "mae_iqd": 978995,
    "missing_cases": 0,
    "scored_cases": 4,
    "scored_days": 120,
    "shortfall_timing": {
      "denominator": 0,
      "numerator": 0,
      "rate": null
    },
    "worst_day_error_iqd": 2697237
  },
  "conservative": {
    "absolute_error_sum_iqd": 115873978,
    "baseline_comparable_days": 120,
    "baseline_mae_iqd": 666064,
    "false_ok": {
      "available_cases": 4,
      "denominator": 0,
      "eligible_invoices": 4,
      "numerator": 0,
      "rate": null,
      "unavailable_cases": 0
    },
    "mae_iqd": 965616,
    "missing_cases": 0,
    "scored_cases": 4,
    "scored_days": 120,
    "shortfall_timing": {
      "denominator": 0,
      "numerator": 0,
      "rate": null
    },
    "worst_day_error_iqd": 2697237
  },
  "j1_with_expected_false_ok": {
    "available_cases": 4,
    "denominator": 0,
    "eligible_invoices": 4,
    "numerator": 0,
    "rate": null,
    "unavailable_cases": 0
  },
  "seven_day_with_expected_false_ok": {
    "available_cases": 4,
    "denominator": 0,
    "eligible_invoices": 4,
    "numerator": 0,
    "rate": null,
    "unavailable_cases": 0
  },
  "stress": {
    "absolute_error_sum_iqd": 102624478,
    "baseline_comparable_days": 120,
    "baseline_mae_iqd": 666064,
    "false_ok": {
      "available_cases": 4,
      "denominator": 0,
      "eligible_invoices": 4,
      "numerator": 0,
      "rate": null,
      "unavailable_cases": 0
    },
    "mae_iqd": 855204,
    "missing_cases": 0,
    "scored_cases": 4,
    "scored_days": 120,
    "shortfall_timing": {
      "denominator": 0,
      "numerator": 0,
      "rate": null
    },
    "worst_day_error_iqd": 2497237
  }
}
```

Zero denominators are null. No safety target or improvement is assumed.
Development realized CSVs stop at day 90; the prediction tail has no realized data.
Original reports and freeze records are preserved. Later method changes require post-test disclosure.
