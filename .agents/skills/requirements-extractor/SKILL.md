---
name: requirements-extractor
description: >
  Use when given a raw user description of a business technology need.
  Trigger phrases: "we need a system", "looking for software", "help us
  choose", "evaluate vendors", "digital transformation". Output ONLY valid
  JSON — no prose, no markdown fences, no preamble.
---

# Requirements extractor

## Input
Raw natural language from the user.

## Output — return ONLY this JSON, nothing else

{
  "company_profile": {
    "size": "SMB | mid-market | enterprise",
    "industry": "string",
    "region": "string",
    "budget_inr": number | null
  },
  "problem_summary": "string (≤40 words)",
  "required_modules": ["string"],
  "nice_to_have": ["string"],
  "must_avoid": ["string"],
  "current_stack": ["string"],
  "timeline_weeks": number | null,
  "decision_criteria": {
    "cost_weight": 0-10,
    "feature_weight": 0-10,
    "implementation_weight": 0-10,
    "support_weight": 0-10,
    "scalability_weight": 0-10
  },
  "clarification_needed": ["string"]
}

## Rules
- null for anything not stated — never invent.
- budget_inr: convert USD at 84 if given in USD.
- All five weights must sum ≤ 40.
- clarification_needed: list specific gaps. Empty array if input is clear.

