# Synthetic evaluation receipt

Mode: `replay`. Split: `dev`. Reporting: `development_examples_permitted`.
Actual execution: 2026-10-23T07:11:55.650317+00:00 to 2026-10-23T07:11:56.330235+00:00.
Code commit: `e5d0bdf8142dc835672c1188fa34528467e7110f`. Model: `synthetic-format-sentinel`.
Dataset SHA-256: `432f4dc71a71bd628e9b5f75a019175195aa3cde43ba864a8fa28140d67d985e`.
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

Post-run changes: `[{"after_run":"evaluation_replay_2026-10-23.json","change":"seed_small_happy_path_parent_before_duplicate_export","original_results_preserved":true,"previous_code_commit":"15abb817c8d9dfa4221546c2bf29f8ab36748ddd","previous_report_sha256":"a2765f7f37dfa35c90c6fb3f7ee389aac7ead73d61e26176876805bf35ee2f86","scope":"development_reconciliation_setup_only_labels_prompts_financial_method_unchanged"},{"after_run":"evaluation_replay_context_2026-10-23.json","change":"accept_proven_figure_aliases_and_margin_plus_coverage_minimum","original_results_preserved":true,"previous_code_commit":"af79b4edae2154ef10f8fddaad36afd35f8a4648","previous_report_sha256":"6d3a074cf828c1ca731ecca672ff3454dc7e280b93e90023babc55871e31fc46","scope":"scorer_semantics_only_no_prompt_financial_method_or_gold_change"},{"after_run":"evaluation_replay_context_2026-10-23.json","change":"normalize_public_seal_metadata_line_endings_for_portable_dataset_hash","original_results_preserved":true,"previous_code_commit":"af79b4edae2154ef10f8fddaad36afd35f8a4648","scope":"private_question_byte_hash_verification_and_original_seal_unchanged"},{"after_run":"evaluation_replay_portable_2026-10-23.json","change":"reset_provider_preference_after_probe_and_between_questions","original_results_preserved":true,"previous_code_commit":"cacae7a665019c8c4c2256b82dc4cb213ea84ff3","scope":"align_evaluator_with_fresh_per_chat_production_client_preserve_attempts_and_pacing"}]`.

Request accounting: `{"provider_requests":0,"synthetic_completions":12}`.

Frozen settings: `{"claims":"unique_renderer_figure_metric_keys_excluding_projections_and_context_dates","compatible_temperature":0,"fallback_model_id":"gpt-6-luna","fallback_provider":"openai","full_development_question_count":32,"input_hash_normalization":"LF_for_public_seal_metadata_only_other_inputs_exact_bytes","intent_observation":"separate_blind_intent_probe","max_agent_completions":4,"max_output_tokens":8192,"max_requests_per_question":6,"max_tool_calls":8,"minimum_spacing_seconds":10,"openai_reasoning":"medium","openai_store":false,"other_joint_fields":"production_response_only_no_probe_repair","primary_model_id":"gemini-3.8-flash","primary_provider":"gemini","provider_preference_lifetime":"production_conversation_only_not_probe_or_prior_questions","replay_sha256":"0f7f4d06daa015249f5e20db22fbaf12c65a0d3d9f986977ef02c9251540bd42","request_limits_by_split":{"dev":96,"heldout":180},"required_fact_policy":"unresolved_question_v1_output_selection","retries_per_provider":1,"timeout_seconds":30,"unknown_historical_claims":"fail_closed"}`.

Reconciliation (seeded development fixtures, separate from Q&A): `{"fixture_count":2,"import_counts":{"duplicate_rows.csv":{"accepted":0,"context_accepted":5,"context_fixture":"small_happy_path.csv","exact_duplicates":3,"flagged_for_review":1},"unmatched_payment.csv":{"accepted":0,"context_accepted":0,"context_fixture":null,"exact_duplicates":0,"flagged_for_review":1}},"metrics":{"combined":{"fn":0,"fp":0,"precision":{"denominator":2,"numerator":2,"rate":1.0},"recall":{"denominator":2,"numerator":2,"rate":1.0},"tp":2},"suspected_duplicate":{"fn":0,"fp":0,"precision":{"denominator":1,"numerator":1,"rate":1.0},"recall":{"denominator":1,"numerator":1,"rate":1.0},"tp":1},"unmatched":{"fn":0,"fp":0,"precision":{"denominator":1,"numerator":1,"rate":1.0},"recall":{"denominator":1,"numerator":1,"rate":1.0},"tp":1}},"scope":"seeded_development_fixtures_not_heldout_questions"}`.

Forecast: archived development only; no new final/unseen run.
Frozen forecast commit: `1dc2179ab1fe80ba799b11c518f1838fb10a523d`.
Forecast summary: `{"base":{"absolute_error_sum_iqd":25596077,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":568802,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":2096402},"conservative":{"absolute_error_sum_iqd":25930847,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":576241,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":2096402},"j1_with_expected_false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":0,"numerator":0,"rate":null,"unavailable_cases":0},"seven_day_with_expected_false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"stress":{"absolute_error_sum_iqd":23100537,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":513345,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":1894402}}`.

Limitations: synthetic_data_only_no_merchant_validation; synthetic_replay_is_protocol_testing_not_model_quality; customer_period_and_tools_are_actual_production_fields; all_required_figures_and_units_categories_and_context_must_match; unmapped_historical_claims_fail_closed_no_evidence_credit; historical_metrics_do_not_score_projection_accuracy; unavailable_provider_answers_remain_in_full_denominators; no_final_or_unseen_forecast_run_in_historical_mode; zero_denominators_are_null_not_success; question_v1_required_output_selection_awaits_human_decision.

Development failures (not held-out examples):
