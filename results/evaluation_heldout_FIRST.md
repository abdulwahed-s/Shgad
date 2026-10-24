# Synthetic evaluation receipt

Mode: `live`. Split: `heldout`. Reporting: `aggregate_only`.
Actual execution: 2026-10-23T19:38:00.473478+00:00 to 2026-10-23T20:18:19.015754+00:00.
Code commit: `4e13092d997d78f4e738ac0f368cfabb7123af3b`. Model: `gemini-3.8-flash+gpt-6-luna`.
Dataset SHA-256: `ec0bf9e54aed942b023b7169a0548d9217988221aab5aca315b39e99bce51754`.
Questions SHA-256: `af854dd2c6d2659cfe08b8b3cbccb3c97b0c38b70308ae12dd3ec1dd012d6609`.
Prompt SHA-256: `c733fa1c16a537a725fc9fc6954cb93b1cbd594e7d5b794716e5c946c2b261d1`.
Intent prompt SHA-256: `3f9c75cb736d40c6c9b7113e5d61de4322cecc3a9cb59c8f2a059c37952d8b58`.
Tool schema SHA-256: `1b3c05edc4445da2ee32fd981accf133f4ea410aa461ce81a15595cc6d3946b8`.

Targets are evaluated against reported counts; no tuning on held-out results.

| Metric | Correct / eligible | Rate |
|---|---:|---:|
| historical_accuracy | 8 / 40 | 0.2 |
| safe_handling | 0 / 20 | 0.0 |
| traceability | 38 / 39 | 0.9743589743589743 |
| joint_accuracy | 12 / 60 | 0.2 |

| Category | Total | Passed | Failed |
|---|---:|---:|---:|
| ambiguous_customer | 3 | 0 | 3 |
| ambiguous_date | 4 | 0 | 4 |
| cash_sufficiency | 3 | 1 | 2 |
| contradictory_records | 3 | 0 | 3 |
| debt_balance | 7 | 2 | 5 |
| drawings_expenses | 2 | 0 | 2 |
| injection | 4 | 0 | 4 |
| invalid_date | 2 | 0 | 2 |
| margin | 3 | 0 | 3 |
| missing_data | 2 | 0 | 2 |
| reconciliation | 4 | 0 | 4 |
| relative_dates | 4 | 1 | 3 |
| sales | 5 | 1 | 4 |
| supplier_dues | 6 | 3 | 3 |
| unsupported_request | 4 | 0 | 4 |
| weekly_summary | 4 | 0 | 4 |

Aggregate failure counts: `{"intent_probe_failed":14,"request_budget_exhausted":20,"unsafe_or_wrong_decision":20,"unsupported_claim":1,"whole_question_incorrect":32,"wrong_customer":13,"wrong_intent":34,"wrong_period":38,"wrong_tool":22}`.

Target assessment: `{"historical_accuracy":{"assessed":true,"met":false,"target":0.95},"joint_accuracy":{"assessed":true,"met":false,"target":0.9},"safe_handling":{"assessed":true,"met":false,"target":0.95},"traceability":{"assessed":true,"met":false,"target":1.0}}`.

Post-run changes: `[{"after_run":"evaluation_replay_2026-10-23.json","change":"seed_small_happy_path_parent_before_duplicate_export","original_results_preserved":true,"previous_code_commit":"15abb817c8d9dfa4221546c2bf29f8ab36748ddd","previous_report_sha256":"a2765f7f37dfa35c90c6fb3f7ee389aac7ead73d61e26176876805bf35ee2f86","scope":"development_reconciliation_setup_only_labels_prompts_financial_method_unchanged"},{"after_run":"evaluation_replay_context_2026-10-23.json","change":"accept_proven_figure_aliases_and_margin_plus_coverage_minimum","original_results_preserved":true,"previous_code_commit":"af79b4edae2154ef10f8fddaad36afd35f8a4648","previous_report_sha256":"6d3a074cf828c1ca731ecca672ff3454dc7e280b93e90023babc55871e31fc46","scope":"scorer_semantics_only_no_prompt_financial_method_or_gold_change"},{"after_run":"evaluation_replay_context_2026-10-23.json","change":"normalize_public_seal_metadata_line_endings_for_portable_dataset_hash","original_results_preserved":true,"previous_code_commit":"af79b4edae2154ef10f8fddaad36afd35f8a4648","scope":"private_question_byte_hash_verification_and_original_seal_unchanged"},{"after_run":"evaluation_replay_portable_2026-10-23.json","change":"reset_provider_preference_after_probe_and_between_questions","original_results_preserved":true,"previous_code_commit":"cacae7a665019c8c4c2256b82dc4cb213ea84ff3","scope":"align_evaluator_with_fresh_per_chat_production_client_preserve_attempts_and_pacing"},{"after_run":"evaluation_replay_client_lifecycle_2026-10-23.json","change":"D50_require_independent_sealed_figure_selectors_for_live_grading","original_results_preserved":true,"previous_code_commit":"e5d0bdf8142dc835672c1188fa34528467e7110f","previous_report_sha256":"0cf92aa3dcf12cfb9123472c03f4d8e4035e12e794a7a022e099090f603fd124","scope":"original_questions_and_seal_unchanged_no_builder_annotations_or_provider_calls"},{"after_run":"evaluation_replay_sealed_requirements_2026-10-23.json","change":"add_standalone_cash_on_hand_selector_from_FINANCIAL_RULES_2","original_results_preserved":true,"previous_code_commit":"5647fc1ef7263218afcff37714b4d24b567c01c2","previous_report_sha256":"a0f094aecad331c62edb9f39c69b022d040472173426b8bcde88b16e48284340","scope":"independent_annotation_format_request_only_no_private_questions_or_outcomes_viewed"},{"after_run":"evaluation_replay_cash_selector_2026-10-23.json","change":"adopt_approved_ten_historical_closing_selectors_and_public_reviewed_seals","original_results_preserved":true,"previous_code_commit":"783592d3d2a37bc1e66c60a4642a3cf58fc76560","previous_report_sha256":"a115b49d939e55e59f0161481aac8285bf8388f085202795390b3661f3f57e14","scope":"independent_scorer_only_no_prompt_application_forecast_or_original_question_change"}]`.

Request accounting: `{"http_status_counts":{"200":68,"401":35,"429":57,"transport_failure":20},"max_requests":180,"max_requests_per_question":6,"minimum_spacing_seconds":10,"provider_requests":180,"request_limit_hits":1,"requests_by_provider_model":{"gemini/gemini-3.8-flash":145,"openai/gpt-6-luna":35}}`.

Frozen settings: `{"claims":"unique_renderer_figure_metric_keys_excluding_projections_and_context_dates","compatible_temperature":0,"fallback_model_id":"gpt-6-luna","fallback_provider":"openai","historical_aliases":"none","historical_completeness":"frozen_allowlisted_observed_package_only","historical_opening_baseline_policy":"allowlisted_observed_baseline_from_economic_date","historical_scope":"original_resolved_economic_period_and_question_knowledge_cutoff","input_hash_normalization":"LF_for_public_seal_metadata_only_other_inputs_exact_bytes","intent_observation":"separate_blind_intent_probe","max_agent_completions":4,"max_output_tokens":8192,"max_requests_per_question":6,"max_tool_calls":8,"minimum_spacing_seconds":10,"openai_reasoning":"medium","openai_store":false,"other_joint_fields":"production_response_only_no_probe_repair","primary_model_id":"gemini-3.8-flash","primary_provider":"gemini","provider_preference_lifetime":"production_conversation_only_not_probe_or_prior_questions","request_limits_by_split":{"dev":96,"heldout":180},"required_fact_policy":"independent_sealed_figure_selectors_v1_D50","retries_per_provider":1,"timeout_seconds":30,"unknown_historical_claims":"fail_closed"}`.

Requirement seal: `{"answer_count":40,"counts_by_behavior":{"answer":40,"clarify":11,"refuse":9},"generator_model_id":"not_exposed","generator_tool":"Codex independent annotation agents and local JSON assembly","human_reviewed":true,"independent_of_build":true,"manifest_sha256":"87129e3d28b2521830e45bb60c04e583af69060332807095b3a5f9f48fca59fd","question_sha256":"af854dd2c6d2659cfe08b8b3cbccb3c97b0c38b70308ae12dd3ec1dd012d6609","reviewed_at":"2026-10-23T17:56:33.119639+00:00","reviewed_count":60,"schema_version":"shgad-requirements-v1","selector_spec_sha256":"cdf840db3adab966e71021f9b6d103f4e845f07a4cb4b0aa498ae4aea20b73af","sha256":"923c9b14003d0df9316f3c72ced001d2cc1ee6805ac2276b63e6f34c4e41a746","split":"heldout","status":"sealed","total_count":60}`.

Reconciliation (seeded development fixtures, separate from Q&A): `{"fixture_count":2,"import_counts":{"duplicate_rows.csv":{"accepted":0,"context_accepted":5,"context_fixture":"small_happy_path.csv","exact_duplicates":3,"flagged_for_review":1},"unmatched_payment.csv":{"accepted":0,"context_accepted":0,"context_fixture":null,"exact_duplicates":0,"flagged_for_review":1}},"metrics":{"combined":{"fn":0,"fp":0,"precision":{"denominator":2,"numerator":2,"rate":1.0},"recall":{"denominator":2,"numerator":2,"rate":1.0},"tp":2},"suspected_duplicate":{"fn":0,"fp":0,"precision":{"denominator":1,"numerator":1,"rate":1.0},"recall":{"denominator":1,"numerator":1,"rate":1.0},"tp":1},"unmatched":{"fn":0,"fp":0,"precision":{"denominator":1,"numerator":1,"rate":1.0},"recall":{"denominator":1,"numerator":1,"rate":1.0},"tp":1}},"scope":"seeded_development_fixtures_not_heldout_questions"}`.

Forecast: archived development only; no new final/unseen run.
Frozen forecast commit: `1dc2179ab1fe80ba799b11c518f1838fb10a523d`.
Forecast summary: `{"base":{"absolute_error_sum_iqd":25596077,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":568802,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":2096402},"conservative":{"absolute_error_sum_iqd":25930847,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":576241,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":2096402},"j1_with_expected_false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":0,"numerator":0,"rate":null,"unavailable_cases":0},"seven_day_with_expected_false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"stress":{"absolute_error_sum_iqd":23100537,"baseline_comparable_days":45,"baseline_mae_iqd":231348,"false_ok":{"available_cases":2,"denominator":0,"eligible_invoices":2,"numerator":0,"rate":null,"unavailable_cases":0},"mae_iqd":513345,"missing_cases":0,"scored_cases":2,"scored_days":45,"shortfall_timing":{"denominator":0,"numerator":0,"rate":null},"worst_day_error_iqd":1894402}}`.

Limitations: synthetic_data_only_no_merchant_validation; intent_probe_is_separate_from_production_routing; customer_period_and_tools_are_actual_production_fields; all_required_figures_and_units_categories_and_context_must_match; unmapped_historical_claims_fail_closed_no_evidence_credit; historical_metrics_do_not_score_projection_accuracy; unavailable_provider_answers_remain_in_full_denominators; no_final_or_unseen_forecast_run_in_historical_mode; zero_denominators_are_null_not_success; independent_requirement_annotations_required_for_live_measurement.
