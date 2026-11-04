import 'dart:convert';

// Actual deterministic reply from the fictional observed sample, no provider.
Map<String, dynamic> morningBriefJson() => Map<String, dynamic>.from(
  jsonDecode(r'''{
  "as_of": "2026-09-28",
  "week": {
    "start": "2026-09-28",
    "end": "2026-10-02"
  },
  "cash_on_hand": {
    "amount_iqd": 420000,
    "kind": "verified",
    "label_key": "cash_on_hand",
    "source_ids": [
      "DEMO-01-CNT-090"
    ],
    "formula": "FINANCIAL_RULES §2: latest count/opening + later cash flows",
    "key": "cash_on_hand",
    "query_evidence": null
  },
  "dues_today": {
    "amount_iqd": 0,
    "kind": "verified",
    "label_key": "supplier_dues",
    "source_ids": [],
    "formula": "sum eligible outstanding; overdue receivables excluded from expected",
    "key": "dues_today",
    "query_evidence": {
      "tool": "get_debts",
      "as_of": "2026-09-28",
      "schedule": "dues",
      "start": "2026-09-28",
      "end": "2026-09-28",
      "counterparty_id": null,
      "known_at": "2026-11-04T07:00:00+00:00",
      "matching_obligations": 0
    }
  },
  "dues_week": {
    "amount_iqd": 650000,
    "kind": "verified",
    "label_key": "supplier_dues",
    "source_ids": [
      "DEMO-01-J1-INVOICE"
    ],
    "formula": "sum eligible outstanding; overdue receivables excluded from expected",
    "key": "dues_week",
    "query_evidence": null
  },
  "overdue_total": {
    "amount_iqd": 0,
    "kind": "calculated",
    "label_key": "total_outstanding",
    "source_ids": [],
    "formula": "FINANCIAL_RULES §5/§11: originals - active verified allocations",
    "key": "overdue_total",
    "query_evidence": {
      "tool": "get_debts",
      "as_of": "2026-09-28",
      "filters": {
        "direction": "receivable",
        "overdue_only": true,
        "counterparty_id": null,
        "due_start": null,
        "due_end": null
      },
      "known_at": "2026-11-04T07:00:00+00:00",
      "matching_obligations": 0
    }
  },
  "overdue_customer_count": {
    "key": "overdue_customer_count",
    "value": 0,
    "unit": "count",
    "kind": "calculated",
    "label_key": "overdue_customer_count",
    "source_ids": [],
    "formula": "count distinct customer IDs in verified overdue-only receivables",
    "query_evidence": {
      "tool": "get_debts",
      "as_of": "2026-09-28",
      "filters": {
        "direction": "receivable",
        "overdue_only": true,
        "counterparty_id": null,
        "due_start": null,
        "due_end": null
      },
      "known_at": "2026-11-04T07:00:00+00:00",
      "matching_obligations": 0
    }
  },
  "top_customers": [],
  "open_flags_count": {
    "key": "open_flags_count",
    "value": 2,
    "unit": "count",
    "kind": "calculated",
    "label_key": "brief_flags_count",
    "source_ids": [
      "DEMO-01-00712",
      "DEMO-01-00713",
      "DEMO-01-00721",
      "DEMO-01-00722"
    ],
    "formula": "count verified reconciliation flags whose evidence touches Saturday..today"
  }
}''')
      as Map,
);
