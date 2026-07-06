---
name: scorecard-builder
description: >
  Use when you have a requirements JSON and a vendor array from research.
  Trigger after the research step returns vendor data. Output ONLY valid
  JSON — no prose.
---

# Scorecard builder

## Inputs (both required before calling this skill)
1. requirements — JSON from requirements-extractor
2. vendors — array, each object:
   {
     "name": "string",
     "features": ["string"],
     "pricing_inr_annual": number | null,
     "implementation_weeks": number | null,
     "market_reviews_score": 0-5 | null,
     "known_clients_similar_size": boolean,
     "risks": ["string"]
   }

## Search execution rules
SEARCH_BUDGET: 6 calls maximum, no exceptions.

Before each search call, check both stop conditions:
  STOP IF (a) vendor_count >= 3
  STOP IF (b) calls_used >= 6
If either is true, do not make another search call — proceed immediately
to scoring with whatever vendors you have.

Search sequence:
  Call 1: Read Drive KB doc once. Count matching vendors found. 
           Set kb_vendors = vendors found. Never read the KB again.
  Calls 2-6: One call per missing vendor only.
             Query pattern: "[vendor name] [industry] pricing features [year]"
             OR "[required_module] software [region] [company_size]"
             Never use broad queries like "best ERP software".
             Never search the same vendor twice.

After each search call, update your internal count:
  calls_used = calls_used + 1
  vendor_count = number of vendors with complete data so far

When either stop condition is met, output the vendor array immediately.

## Scoring (per vendor, per dimension, 0-10)
- Cost: 10 if ≤ 60% of budget, linear to 0 at 150%. Null budget → 5.
- Features: (matched_required / total_required) × 10
- Implementation: 10 if ≤ timeline_weeks, −1 per 2 weeks over. Null → 5.
- Support: market_reviews_score × 2
- Scalability: known_clients_similar_size → 10, else 4

Weighted total = Σ(score × weight) / Σ(weights)

## Output — return ONLY this JSON

{
  "search_metadata": {
    "calls_used": number,
    "stop_reason": "vendor_count_met | budget_exhausted",
    "vendors_found": number
  },
  "ranked_vendors": [
    {
      "rank": 1,
      "name": "string",
      "fit_pct": number,
      "dimension_scores": {
        "cost": 0, "features": 0, "implementation": 0,
        "support": 0, "scalability": 0
      },
      "top_3_pros": ["string"],
      "top_3_cons": ["string"],
      "risk_flags": ["string"]
    }
  ],
  "gantt_phases": [
    {
      "phase": "string",
      "owner": "vendor|client|joint",
      "duration_weeks": number,
      "depends_on": "string|null"
    }
  ],
  "overall_risk_level": "low|medium|high",
  "risk_summary": "string (≤60 words)"
}

## Rules
- Always rank every vendor — never drop one silently.
- risk_flags must cite a specific data point.
- Always include: Discovery, Config/Build, UAT, Go-Live, Hypercare phases.
- Flag any required_module with zero vendor coverage as a critical gap.
- If stop_reason is budget_exhausted with fewer than 3 vendors, note this
  explicitly in risk_summary.