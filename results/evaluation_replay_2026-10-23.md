# Synthetic evaluation receipt

Mode: `replay`. Split: `dev`. Reporting: `development_examples_permitted`.
Actual execution: 2026-10-23T06:35:24.582248+00:00 to 2026-10-23T06:35:25.246734+00:00.
Code commit: `15abb817c8d9dfa4221546c2bf29f8ab36748ddd`. Model: `synthetic-format-sentinel`.
Dataset SHA-256: `06f16bb7345a471ddd7200164d31349226da51ddc8564151252f4a0b31f688d6`.
Questions SHA-256: `089b5e89e0c216cd2053eb170db2ef162ff24d538e44d58b31fbcfc6e0e5c3c7`.
Prompt SHA-256: `c733fa1c16a537a725fc9fc6954cb93b1cbd594e7d5b794716e5c946c2b261d1`.
Intent prompt SHA-256: `3f9c75cb736d40c6c9b7113e5d61de4322cecc3a9cb59c8f2a059c37952d8b58`.
Tool schema SHA-256: `1b3c05edc4445da2ee32fd981accf133f4ea410aa461ce81a15595cc6d3946b8`.

Synthetic replay checks exercise the protocol; they are not live-model accuracy results.

| Metric | Correct / eligible | Rate |
|---|---:|---:|
| historical_accuracy | 3 / 3 | 1.0 |
| safe_handling | 1 / 1 | 1.0 |
| traceability | 7 / 7 | 1.0 |
| joint_accuracy | 4 / 4 | 1.0 |

| Category | Total | Passed | Failed |
|---|---:|---:|---:|
| contradictory_records | 1 | 1 | 0 |
| debt_balance | 1 | 1 | 0 |
| margin | 1 | 1 | 0 |
| sales | 1 | 1 | 0 |

Aggregate failure counts: `{}`.

Target assessment: `{"historical_accuracy":{"assessed":false,"met":null,"target":0.95},"joint_accuracy":{"assessed":false,"met":null,"target":0.9},"safe_handling":{"assessed":false,"met":null,"target":0.95},"traceability":{"assessed":false,"met":null,"target":1.0}}`.

Request accounting: `{"provider_requests":0,"synthetic_completions":12}`.

Frozen settings: `{"claims":"unique_renderer_figure_metric_keys_excluding_projections_and_context_dates","compatible_temperature":0,"fallback_model_id":"gpt-6-luna","fallback_provider":"openai","full_development_question_count":32,"intent_observation":"separate_blind_intent_probe","max_agent_completions":4,"max_output_tokens":8192,"max_requests_per_question":6,"max_tool_calls":8,"minimum_spacing_seconds":10,"openai_reasoning":"medium","openai_store":false,"other_joint_fields":"production_response_only_no_probe_repair","primary_model_id":"gemini-3.8-flash","primary_provider":"gemini","replay_sha256":"0f7f4d06daa015249f5e20db22fbaf12c65a0d3d9f986977ef02c9251540bd42","request_limits_by_split":{"dev":96,"heldout":180},"retries_per_provider":1,"timeout_seconds":30,"unknown_historical_claims":"fail_closed"}`.

Reconciliation (seeded development fixtures, separate from Q&A): `{"fixture_count":2,"import_counts":{"duplicate_rows.csv":{"accepted":1,"exact_duplicates":1,"flagged_for_review":2},"unmatched_payment.csv":{"accepted":0,"exact_duplicates":0,"flagged_for_review":1}},"metrics":{"combined":{"fn":0,"fp":2,"precision":{"denominator":4,"numerator":2,"rate":0.5},"recall":{"denominator":2,"numerator":2,"rate":1.0},"tp":2},"suspected_duplicate":{"fn":0,"fp":0,"precision":{"denominator":1,"numerator":1,"rate":1.0},"recall":{"denominator":1,"numerator":1,"rate":1.0},"tp":1},"unmatched":{"fn":0,"fp":2,"precision":{"denominator":3,"numerator":1,"rate":0.3333333333333333},"recall":{"denominator":1,"numerator":1,"rate":1.0},"tp":1}},"scope":"seeded_development_fixtures_not_heldout_questions"}`.

Forecast: archived development only; no new final/unseen run.
Frozen forecast commit: `1dc2179ab1fe80ba799b11c518f1838fb10a523d`.
Forecast summary: `{"base":{"absolute_error_sum_iqd":25596077,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":568802,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":2096402},"conservative":{"absolute_error_sum_iqd":25930847,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":576241,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":2096402},"j1_with_expected_false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":0,"numerator":0,"rate":null,"unavailable_cases":0},"seven_day_with_expected_false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"stress":{"absolute_error_sum_iqd":23100537,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":513345,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":1894402}}`.

Limitations: synthetic_data_only_no_merchant_validation; synthetic_replay_is_protocol_testing_not_model_quality; customer_period_and_tools_are_actual_production_fields; all_required_figures_and_units_categories_and_context_must_match; unmapped_historical_claims_fail_closed_no_evidence_credit; historical_metrics_do_not_score_projection_accuracy; unavailable_provider_answers_remain_in_full_denominators; no_final_or_unseen_forecast_run_in_historical_mode; zero_denominators_are_null_not_success.

Development failures (not held-out examples):
