# ruff: noqa
# Copyright 2026 Google LLC

import os
import httpx
import google.auth
from dotenv import load_dotenv

# Explicitly load .env file from the project root (parent of 'app')
_project_root = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(_project_root, ".env"), override=True)
from pydantic import BaseModel, Field
from typing import Any, AsyncGenerator

from google.adk.agents import Agent, LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import Gemini
from google.adk.workflow import Edge, Workflow, node, FunctionNode, START
from google.adk.events.event import Event, EventActions
from google.adk.events.request_input import RequestInput
from google.genai import types

# The ADK and google-genai SDK will automatically pick up GEMINI_API_KEY from the .env file.

# ---------------------------------------------------------
# 1. Schemas & Models
# ---------------------------------------------------------


class CompanyProfile(BaseModel):
    size: str = Field(
        default="SMB",
        description="Company size: SMB | mid-market | enterprise.",
    )
    industry: str | None = Field(default=None, description="Industry sector.")
    region: str | None = Field(default=None, description="Geographic region.")
    budget_inr: float | None = Field(
        default=None,
        description="Budget in INR. Convert USD at 84 if given in USD. Null if not stated.",
    )


class DecisionCriteria(BaseModel):
    cost_weight: int = Field(default=5, ge=0, le=10)
    feature_weight: int = Field(default=5, ge=0, le=10)
    implementation_weight: int = Field(default=5, ge=0, le=10)
    support_weight: int = Field(default=5, ge=0, le=10)
    scalability_weight: int = Field(default=5, ge=0, le=10)


class RequirementsOutput(BaseModel):
    company_profile: CompanyProfile = Field(default_factory=CompanyProfile)
    problem_summary: str = Field(
        default="", description="Problem summary in 40 words or fewer."
    )
    required_modules: list[str] = Field(
        default=[],
        description="Modules/features explicitly required.",
    )
    nice_to_have: list[str] = Field(
        default=[], description="Features that are desired but not mandatory."
    )
    must_avoid: list[str] = Field(
        default=[], description="Vendors, features, or patterns to explicitly exclude."
    )
    current_stack: list[str] = Field(
        default=[], description="Existing tools/systems already in use."
    )
    timeline_weeks: int | None = Field(
        default=None, description="Expected implementation timeline in weeks."
    )
    decision_criteria: DecisionCriteria = Field(default_factory=DecisionCriteria)
    clarification_needed: list[str] = Field(
        default=[],
        description="Specific gaps to clarify. Empty array if input is clear.",
    )


class VendorDetail(BaseModel):
    name: str
    features: list[str] = Field(description="List of features/modules offered.")
    pricing_inr_annual: float | None = Field(
        default=None, description="Annual pricing in INR."
    )
    implementation_weeks: int | None = Field(
        default=None, description="Implementation timeline in weeks."
    )
    market_reviews_score: float | None = Field(
        default=None, description="G2 or Capterra review score (0-5)."
    )
    known_clients_similar_size: bool = Field(
        default=False,
        description="True if they serve companies of similar size and industry.",
    )
    risks: list[str] = Field(description="Top 3 reported risks or complaints.")


class ResearchOutput(BaseModel):
    vendors: list[VendorDetail] = Field(default=[])


class DimensionScores(BaseModel):
    cost: float
    features: float
    implementation: float
    support: float
    scalability: float


class RankedVendor(BaseModel):
    rank: int
    name: str
    fit_pct: float
    dimension_scores: DimensionScores
    top_3_pros: list[str]
    top_3_cons: list[str]
    risk_flags: list[str]


class GanttPhase(BaseModel):
    phase: str
    owner: str  # 'vendor' | 'client' | 'joint'
    duration_weeks: int
    depends_on: str | None = None


class ScorecardOutput(BaseModel):
    ranked_vendors: list[RankedVendor] = Field(default=[])
    gantt_phases: list[GanttPhase] = Field(default=[])
    overall_risk_level: str
    risk_summary: str


# ---------------------------------------------------------
# 2. Mock MCP Tools (Google Drive, Google Docs, Serper Search)
# ---------------------------------------------------------


def read_vendor_kb(doc_id: str) -> dict:
    """Reads the vendor knowledge base from Google Drive.

    Args:
        doc_id: The Google Drive document ID.

    Returns:
        A dictionary containing pre-existing vendor data.
    """
    # Return pre-existing template knowledge base data
    return {
        "Odoo": {
            "features": ["ERP", "CRM", "Inventory", "HR", "Accounting"],
            "annual_pricing_usd": 12000,
            "timeline_weeks": 10,
            "review_score": 4.4,
            "risks": ["Complexity", "Customization cost", "App dependencies"],
        },
        "SAP Business One": {
            "features": ["ERP", "Finance", "Inventory", "Procurement"],
            "annual_pricing_usd": 50000,
            "timeline_weeks": 26,
            "review_score": 4.1,
            "risks": ["Extremely high cost", "Rigid processes", "Partner dependent"],
        },
        "Microsoft Dynamics 365": {
            "features": ["ERP", "CRM", "Finance", "Supply Chain", "Sales"],
            "annual_pricing_usd": 40000,
            "timeline_weeks": 20,
            "review_score": 4.3,
            "risks": ["Complex licensing", "Steep learning curve", "Integration challenges"],
        },
        "Oracle NetSuite": {
            "features": ["ERP", "Financials", "CRM", "E-commerce"],
            "annual_pricing_usd": 45000,
            "timeline_weeks": 24,
            "review_score": 4.2,
            "risks": ["High implementation cost", "Difficult to customize", "Poor customer support"],
        },
        "Salesforce": {
            "features": ["CRM", "Sales", "Service", "Marketing", "Commerce"],
            "annual_pricing_usd": 30000,
            "timeline_weeks": 12,
            "review_score": 4.5,
            "risks": ["Expensive add-ons", "Data storage limits", "Requires specialized admins"],
        },
    }


async def serper_search(query: str) -> dict:
    """Searches the web using serper.dev.

    Args:
        query: The search query string.

    Returns:
        A dictionary with search results.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key or "your_serper" in api_key:
        # Return fallback results for local testing/smoke tests
        return {
            "results": [
                {
                    "title": "Odoo ERP - Open Source Business Apps",
                    "snippet": "Odoo is a suite of open source business apps. Ideal for SMEs.",
                },
                {
                    "title": "SAP Business One ERP for Small Businesses",
                    "snippet": "SAP Business One is an ERP system designed for small and medium enterprises.",
                },
                {
                    "title": "Microsoft Dynamics 365 - CRM & ERP",
                    "snippet": "A product line of enterprise resource planning and customer relationship management applications.",
                },
                {
                    "title": "Oracle NetSuite: Cloud Accounting & ERP Software",
                    "snippet": "NetSuite is a cloud business software suite for ERP, CRM, and e-commerce.",
                },
                {
                    "title": "Salesforce: The Customer Company",
                    "snippet": "Salesforce provides customer relationship management software and applications.",
                },
                {
                    "title": "Custom Software Development Cost and Timelines",
                    "snippet": "Custom dev typically costs 50,000 to 250,000 USD and takes 6-12 months.",
                },
            ]
        }

    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://google.serper.dev/search",
                headers=headers,
                json={"q": query},
                timeout=10.0,
            )
            return response.json()
        except Exception:
            return {"results": []}


def get_docs_service():
    """Helper to authenticate and return Google Docs API service."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import google.auth
    
    scopes = ["https://www.googleapis.com/auth/documents"]
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=scopes)
    else:
        creds, _ = google.auth.default(scopes=scopes)
    return build('docs', 'v1', credentials=creds)


def create_google_doc(title: str, content: str) -> str:
    """Appends the report content to the existing Google Doc.

    Args:
        title: The title of the document.
        content: The report content in markdown/prose.

    Returns:
        The shareable link to the Google Doc.
    """
    doc_id = os.environ.get("KB_DOC_ID", "1MdOp95oLWAXjrVxcMDDiDPscDIJUprwVQ45ihK1TNf8")
    try:
        service = get_docs_service()
        requests = [
            {
                'insertText': {
                    'endOfSegmentLocation': {
                        'segmentId': ''
                    },
                    'text': f"\n\n========================================\n{title}\n========================================\n\n{content}\n"
                }
            }
        ]
        service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
    except Exception as e:
        print(f"Error appending report to Google Doc: {e}")
        
    return f"https://docs.google.com/document/d/{doc_id}/edit?usp=sharing"


def append_to_kb_doc(doc_id: str, summary: str) -> str:
    """Appends a one-line run summary to the Drive Knowledge Base document.

    Args:
        doc_id: The Knowledge Base document ID.
        summary: The one-line summary to append.

    Returns:
        Status message indicating success.
    """
    try:
        service = get_docs_service()
        requests = [
            {
                'insertText': {
                    'endOfSegmentLocation': {
                        'segmentId': ''
                    },
                    'text': f"\nSummary: {summary}\n"
                }
            }
        ]
        service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        return f"Successfully appended summary to KB doc {doc_id}."
    except Exception as e:
        print(f"Error appending summary to Google Doc: {e}")
        return f"Failed to append to KB doc: {e}"


# ---------------------------------------------------------
# 3. Step Agents (Requirements Extractor & Scorecard Builder)
# ---------------------------------------------------------

requirements_extractor = LlmAgent(
    name="requirements_extractor",
    rerun_on_resume=True,
    model=Gemini(model="gemini-2.5-flash"),
    instruction=(
        "You are a requirements extraction agent. Given a raw user description of a business technology need, "
        "extract structured information and return ONLY valid JSON matching the output schema — no prose, no markdown fences, no preamble.\n\n"
        "Rules:\n"
        "- Set null for anything not stated; never invent values.\n"
        "- budget_inr: if given in USD, convert at 84. Leave null if not stated.\n"
        "- All five decision_criteria weights must sum to ≤ 40.\n"
        "- clarification_needed: list specific gaps. Use empty array if the input is clear enough to proceed."
    ),
    output_schema=RequirementsOutput,
)

scorecard_builder = LlmAgent(
    name="scorecard_builder",
    rerun_on_resume=True,
    model=Gemini(model="gemini-2.5-flash"),
    instruction=(
        "You are a vendor scoring agent. Given a requirements JSON and a vendors array, compute fit scores per vendor and return ONLY valid JSON — no prose.\n\n"
        "Scoring rules (0-10 per dimension):\n"
        "- cost: 10 if pricing ≤ 60% of budget_inr, linear to 0 at 150%. budget_inr null → 5.\n"
        "- features: (matched required_modules / total required_modules) × 10.\n"
        "- implementation: 10 if ≤ timeline_weeks, −1 per 2 weeks over. timeline_weeks null → 5.\n"
        "- support: market_reviews_score × 2.\n"
        "- scalability: known_clients_similar_size → 10, else 4.\n"
        "fit_pct = weighted sum using decision_criteria weights / sum of weights × 10 (converted to 0-100).\n\n"
        "Rules:\n"
        "- Always rank every vendor — never drop one silently.\n"
        "- risk_flags must cite a specific data point from the vendor data.\n"
        "- Always include exactly these Gantt phases: Discovery, Config/Build, UAT, Go-Live, Hypercare.\n"
        "- Flag any required_module with zero vendor coverage as a critical gap in risk_summary."
    ),
    output_schema=ScorecardOutput,
)

# ---------------------------------------------------------
# 4. ADK 2.0 Graph Workflow Nodes and Edges
# ---------------------------------------------------------


async def intake_node(ctx: Any, node_input: Any):
    """Step 1 — Intake step that handles clarification loop."""
    # Convert node_input to string safely (handling Gemini Part structures)
    input_str = ""
    if node_input:
        if hasattr(node_input, "parts") and node_input.parts:
            input_str = "".join(part.text for part in node_input.parts if hasattr(part, "text")).strip()
        else:
            input_str = str(node_input).strip()

    if "raw_message" not in ctx.state:
        # First run: node_input is the initial message
        ctx.state["raw_message"] = input_str
        ctx.state["clarification_history"] = []
    else:
        # Subsequent runs: node_input is the user's answer
        # Avoid appending empty answers, original messages, or duplicates on re-run
        raw_msg = str(ctx.state.get("raw_message", "")).strip()
        if input_str and input_str != raw_msg:
            history = ctx.state.setdefault("clarification_history", [])
            if not history or history[-1] != input_str:
                history.append(input_str)

    # Accumulate full context
    full_context = f"Initial message: {ctx.state['raw_message']}\n"
    for i, answer in enumerate(ctx.state.get("clarification_history", [])):
        full_context += f"Clarification response {i + 1}: {answer}\n"

    # Write to debug file
    with open("debug_flow.txt", "a", encoding="utf-8") as f:
        f.write(f"\n--- INTAKE NODE ---\n")
        f.write(f"node_input: {node_input}\n")
        f.write(f"extracted input_str: {input_str}\n")
        f.write(f"state raw_message: {ctx.state.get('raw_message')}\n")
        f.write(f"state clarification_history: {ctx.state.get('clarification_history')}\n")
        f.write(f"full_context passed to LLM:\n{full_context}\n")

    # Run the extractor agent
    req_output = await ctx.run_node(requirements_extractor, node_input=full_context)

    # Store requirements in state
    ctx.state["requirements"] = req_output
    
    with open("debug_flow.txt", "a", encoding="utf-8") as f:
        f.write(f"requirements_extractor output: {req_output}\n")

    yield Event(output=req_output)


def clarification_gate(ctx: Any, node_input: Any):
    """Router node to check if clarification is needed."""
    requirements = ctx.state.get("requirements", {})
    questions = (
        requirements.get("clarification_needed", [])
        if isinstance(requirements, dict)
        else requirements.clarification_needed
    )

    if questions:
        combined_questions = "\n".join(questions)
        return Event(output=combined_questions, actions=EventActions(route="clarify"))
    return Event(output=requirements, actions=EventActions(route="proceed"))


async def clarification_asker(ctx: Any, node_input: Any):
    """HITL step yielding RequestInput to pause and get user reply."""
    with open("debug_flow.txt", "a", encoding="utf-8") as f:
        f.write(f"\n--- CLARIFICATION ASKER (Before yield) ---\n")
        f.write(f"node_input: {node_input}\n")
        
    yield RequestInput(interrupt_id="clarification", message=str(node_input))


async def research_node(ctx: Any, node_input: Any):
    """Step 2 — Research step utilizing Google Drive KB and Serper Search."""
    requirements = ctx.state.get("requirements", {})
    req_modules = (
        requirements.get("required_modules", [])
        if isinstance(requirements, dict)
        else requirements.required_modules
    )
    budget_inr = (
        (requirements.get("company_profile") or {}).get("budget_inr")
        if isinstance(requirements, dict)
        else requirements.company_profile.budget_inr
    )
    timeline_weeks = (
        requirements.get("timeline_weeks")
        if isinstance(requirements, dict)
        else requirements.timeline_weeks
    )

    doc_id = os.environ.get("KB_DOC_ID", "default-kb-doc-id")
    kb_data = read_vendor_kb(doc_id)

    # Search for additional details
    search_query = (
        f"top erp software features timeline pricing risks for {' '.join(req_modules)}"
    )
    search_results = await serper_search(search_query)

    # Compile the vendor detail list
    vendors = []
    
    # 1. Add vendors from Knowledge Base
    for vendor_name, data in kb_data.items():
        vendors.append(
            VendorDetail(
                name=vendor_name,
                features=data["features"],
                pricing_inr_annual=data["annual_pricing_usd"] * 85.0,  # Convert USD to INR
                implementation_weeks=data["timeline_weeks"],
                market_reviews_score=data["review_score"],
                known_clients_similar_size=True,
                risks=data["risks"],
            )
        )

    # 2. Add Custom Dev option
    vendors.append(
        VendorDetail(
            name="Custom Development",
            features=req_modules,
            pricing_inr_annual=7500000.0,
            implementation_weeks=36,
            market_reviews_score=4.5,
            known_clients_similar_size=True,
            risks=[
                "High initial cost",
                "Long delivery timeline",
                "Maintenance overhead",
            ],
        )
    )

    research_output = ResearchOutput(vendors=vendors)
    ctx.state["research"] = research_output.model_dump()
    yield Event(output=research_output.model_dump())


async def score_rank_node(ctx: Any, node_input: Any):
    """Step 3 — Score and rank using Scorecard Builder."""
    import json

    reqs = ctx.state.get("requirements", {})
    research = ctx.state.get("research", {})
    vendors = research.get("vendors", []) if isinstance(research, dict) else []

    # Pass requirements JSON + vendor array as a structured prompt
    skill_input = json.dumps(
        {"requirements": reqs, "vendors": vendors}, ensure_ascii=False, indent=2
    )
    scorecard = await ctx.run_node(scorecard_builder, node_input=skill_input)
    ctx.state["scorecard"] = scorecard
    yield Event(output=scorecard)


async def write_deliver_node(ctx: Any, node_input: Any):
    """Step 4 — Write report, create Google Doc, append to KB, and deliver summary."""
    scorecard = ctx.state.get("scorecard", {})
    ranked_vendors = (
        scorecard.get("ranked_vendors", [])
        if isinstance(scorecard, dict)
        else scorecard.ranked_vendors
    )
    gantt_phases = (
        scorecard.get("gantt_phases", [])
        if isinstance(scorecard, dict)
        else scorecard.gantt_phases
    )
    overall_risk_level = (
        scorecard.get("overall_risk_level", "medium")
        if isinstance(scorecard, dict)
        else scorecard.overall_risk_level
    )
    risk_summary = (
        scorecard.get("risk_summary", "")
        if isinstance(scorecard, dict)
        else scorecard.risk_summary
    )

    # Generate Report Content
    top_vendor = ranked_vendors[0] if ranked_vendors else None
    top_name = (
        top_vendor.get("name") if isinstance(top_vendor, dict) else top_vendor.name
    )
    top_score = (
        top_vendor.get("fit_pct")
        if isinstance(top_vendor, dict)
        else top_vendor.fit_pct
    )

    executive_summary = (
        f"Based on the analysis, {top_name} is the top recommendation for your business. "
        f"It matches your feature requirements with an overall fit score of {top_score}%. "
        f"The risk profile is evaluated as {overall_risk_level.upper()}."
    )

    report_markdown = (
        f"# Technology Evaluation Report\n\n"
        f"## 1. Executive Summary\n{executive_summary}\n\n"
        f"## 2. Ranked Vendor Comparison Table\n"
        f"| Rank | Vendor | Fit Score | Pros | Cons | Risk Flags |\n"
        f"|---|---|---|---|---|---|\n"
    )

    for v in ranked_vendors:
        rank = v.get("rank") if isinstance(v, dict) else v.rank
        name = v.get("name") if isinstance(v, dict) else v.name
        score = v.get("fit_pct") if isinstance(v, dict) else v.fit_pct
        pros = (
            ", ".join(v.get("top_3_pros", []))
            if isinstance(v, dict)
            else ", ".join(v.top_3_pros)
        )
        cons = (
            ", ".join(v.get("top_3_cons", []))
            if isinstance(v, dict)
            else ", ".join(v.top_3_cons)
        )
        risks = (
            ", ".join(v.get("risk_flags", []))
            if isinstance(v, dict)
            else ", ".join(v.risk_flags)
        )
        report_markdown += (
            f"| {rank} | {name} | {score}% | {pros} | {cons} | {risks} |\n"
        )

    report_markdown += (
        f"\n## 3. Dimension-by-Dimension Breakdown\n"
        f"Evaluation performed across modules compatibility, pricing alignment, and timeline feasibility.\n\n"
        f"## 4. Risk Assessment\n"
        f"**Overall Risk Level**: {overall_risk_level.upper()}\n"
        f"**Summary**: {risk_summary}\n\n"
        f"## 5. Recommended Implementation Gantt\n"
        f"| Phase | Owner | Duration (Weeks) | Depends On |\n"
        f"|---|---|---|---|\n"
    )

    for phase in gantt_phases:
        p_name = phase.get("phase") if isinstance(phase, dict) else phase.phase
        p_owner = phase.get("owner") if isinstance(phase, dict) else phase.owner
        p_duration = (
            phase.get("duration_weeks")
            if isinstance(phase, dict)
            else phase.duration_weeks
        )
        p_depends = (
            phase.get("depends_on") if isinstance(phase, dict) else phase.depends_on
        )
        report_markdown += (
            f"| {p_name} | {p_owner} | {p_duration} | {p_depends or '-'} |\n"
        )

    report_markdown += (
        f"\n## 6. Next Steps\nSchedule demo sessions with the top recommended vendor."
    )

    # Create Google Doc and append to KB
    doc_link = create_google_doc(
        "Technology Selection Evaluation Report", report_markdown
    )
    doc_id = os.environ.get("KB_DOC_ID", "default-kb-doc-id")
    append_to_kb_doc(
        doc_id,
        f"Evaluated tech options for requirements. Top choice: {top_name} ({top_score}%).",
    )

    final_reply = (
        f"**Executive Summary**\n{executive_summary}\n\n"
        f"**Top Recommendation**: {top_name} (Fit Score: {top_score}%)\n\n"
        f"**Full Evaluation Report**: [Google Doc Link]({doc_link})"
    )

    yield Event(
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=final_reply)]
        ),
        output=final_reply,
    )


# Wrap all node functions as FunctionNode instances
intake_fn = FunctionNode(func=intake_node, rerun_on_resume=True)
gate_fn = FunctionNode(func=clarification_gate, rerun_on_resume=False)
ask_fn = FunctionNode(func=clarification_asker, rerun_on_resume=False)
research_fn = FunctionNode(func=research_node, rerun_on_resume=False)
score_fn = FunctionNode(func=score_rank_node, rerun_on_resume=True)
deliver_fn = FunctionNode(func=write_deliver_node, rerun_on_resume=False)

# Define the workflow graph topology
root_agent = Workflow(
    name="smart_tech_navigator_workflow",
    edges=[
        (START, intake_fn),
        (intake_fn, gate_fn),
        Edge(from_node=gate_fn, to_node=ask_fn, route="clarify"),
        (ask_fn, intake_fn),
        Edge(from_node=gate_fn, to_node=research_fn, route="proceed"),
        (research_fn, score_fn),
        (score_fn, deliver_fn),
    ],
    rerun_on_resume=True,
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(is_resumable=True),
)
