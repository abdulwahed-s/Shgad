# Synthetic forecast evaluation receipt

Split: `dev`. Actual execution: 2026-10-23T06:35:26.235014+00:00 to 2026-10-23T06:35:27.174983+00:00.
Code commit: `15abb817c8d9dfa4221546c2bf29f8ab36748ddd`. Frozen method commit: `1dc2179ab1fe80ba799b11c518f1838fb10a523d`.
Dataset SHA-256: `2b09c5b5f536e6abb3bdff879edc737f5f7fa178c9ce4bf9212cbe6f5ebad5f0`. Model: `deterministic-no-llm`.
No provider request. Synthetic forecasting, no merchant validation.

| Shop | Cutoff | Predicted days per series | Scored days per series |
|---|---:|---:|---:|
| primary | 60 | 30 | 30 |
| primary | 75 | 30 | 15 |

Scored-day-weighted metrics, baseline comparison, first-shortfall ±2 days and false-OK numerator/realized-short denominator/rate:

```json
{
  "base": {
    "absolute_error_sum_iqd": 25596077,
    "baseline_comparable_days": 45,
    "baseline_mae_iqd": 231348,
    "false_ok": {
      "available_cases": 2,
      "denominator": 0,
      "eligible_invoices": 2,
      "numerator": 0,
      "rate": null,
      "unavailable_cases": 0
    },
    "mae_iqd": 568802,
    "missing_cases": 0,
    "scored_cases": 2,
    "scored_days": 45,
    "shortfall_timing": {
      "denominator": 0,
      "numerator": 0,
      "rate": null
    },
    "worst_day_error_iqd": 2096402
  },
  "conservative": {
    "absolute_error_sum_iqd": 25930847,
    "baseline_comparable_days": 45,
    "baseline_mae_iqd": 231348,
    "false_ok": {
      "available_cases": 2,
      "denominator": 0,
      "eligible_invoices": 2,
      "numerator": 0,
      "rate": null,
      "unavailable_cases": 0
    },
    "mae_iqd": 576241,
    "missing_cases": 0,
    "scored_cases": 2,
    "scored_days": 45,
    "shortfall_timing": {
      "denominator": 0,
      "numerator": 0,
      "rate": null
    },
    "worst_day_error_iqd": 2096402
  },
  "j1_with_expected_false_ok": {
    "available_cases": 2,
    "denominator": 0,
    "eligible_invoices": 0,
    "numerator": 0,
    "rate": null,
    "unavailable_cases": 0
  },
  "seven_day_with_expected_false_ok": {
    "available_cases": 2,
    "denominator": 0,
    "eligible_invoices": 2,
    "numerator": 0,
    "rate": null,
    "unavailable_cases": 0
  },
  "stress": {
    "absolute_error_sum_iqd": 23100537,
    "baseline_comparable_days": 45,
    "baseline_mae_iqd": 231348,
    "false_ok": {
      "available_cases": 2,
      "denominator": 0,
      "eligible_invoices": 2,
      "numerator": 0,
      "rate": null,
      "unavailable_cases": 0
    },
    "mae_iqd": 513345,
    "missing_cases": 0,
    "scored_cases": 2,
    "scored_days": 45,
    "shortfall_timing": {
      "denominator": 0,
      "numerator": 0,
      "rate": null
    },
    "worst_day_error_iqd": 1894402
  }
}
```

Zero denominators are null. No safety target or improvement is assumed.
Development realized CSVs stop at day 90; the prediction tail has no realized data.
Original reports and freeze records are preserved. Later method changes require post-test disclosure.
