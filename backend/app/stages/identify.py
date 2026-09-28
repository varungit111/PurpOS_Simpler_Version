from app.schemas.assessment import AssessmentStage
from app.schemas.conversation import (
    CompletionCriterion,
    CrossCheckTarget,
    QuestionEvidenceArea,
    StageConfig,
)


identify_stage_config = StageConfig(
    stage=AssessmentStage.identify,
    system_instructions=(
        "Gather authentic raw material about the organisation, probe vague or "
        "incomplete answers, and cross-check claims against available evidence."
    ),
    question_requirements=[
        "Ask targeted CORE/SOI discovery questions.",
        "Collect enough context to shape a discovery brief and identify themes.",
        "Probe PESTLE, stakeholder, positioning, contribution and vulnerability areas.",
    ],
    evidence_requirements=[
        "Accept conversation answers as evidence.",
        "Use optional uploaded documents when available.",
        "Keep source references attached to structured findings.",
    ],
    required_structured_fields=[
        "discovery_brief",
        "themes",
        "pestle_findings",
        "stakeholder_insights",
        "positioning_evidence",
        "social_contribution_evidence",
        "vulnerabilities_gaps",
        "open_questions",
        "evidence_references",
    ],
    available_tools=["shared_rag_retrieval"],
    output_schema="IdentifyOutput",
    completion_criteria=[
        CompletionCriterion(
            name="configured_by_orchestrator",
            description=(
                "The orchestrator may decide when Identify is ready to hand off; "
                "no final threshold is defined in this prototype foundation."
            ),
        )
    ],
    cross_check_targets=[
        CrossCheckTarget(
            name="positioning",
            description="Claims about market position, differentiation and customers.",
            fields=["positioning_evidence"],
            keywords=["position", "market", "customer", "different", "competitor"],
        ),
        CrossCheckTarget(
            name="social_contribution",
            description="Claims about social contribution, impact and purpose.",
            fields=["social_contribution_evidence"],
            keywords=["impact", "purpose", "community", "social", "contribution"],
        ),
        CrossCheckTarget(
            name="stakeholders",
            description="Claims about stakeholder needs, tensions and expectations.",
            fields=["stakeholder_insights"],
            keywords=["stakeholder", "employee", "supplier", "partner", "investor"],
        ),
        CrossCheckTarget(
            name="vulnerabilities",
            description="Known weaknesses, risk areas and unresolved gaps.",
            fields=["vulnerabilities_gaps", "open_questions"],
            keywords=["risk", "gap", "weakness", "vulnerable", "challenge"],
        ),
    ],
    question_evidence_areas=[
        QuestionEvidenceArea(
            id="organisation_basics",
            label="Organisation basics",
            question="What does the organisation do, and who does it serve?",
            evidence_prompt="Name the offer, customer group and business context.",
            structured_field="discovery_brief",
            keywords=["do", "serve", "business", "organisation", "organization"],
        ),
        QuestionEvidenceArea(
            id="best_work",
            label="Best work",
            question="What problem does the organisation solve when it is at its best?",
            evidence_prompt=(
                "Describe a concrete example of the organisation at its best."
            ),
            structured_field="themes",
            keywords=["best", "solve", "problem", "strength", "example"],
        ),
        QuestionEvidenceArea(
            id="founding_story",
            label="Founding story",
            question=(
                "Why was the organisation started, and what still feels true today?"
            ),
            evidence_prompt="Connect origin story to current choices or trade-offs.",
            structured_field="themes",
            keywords=["started", "founded", "origin", "story", "why"],
        ),
        QuestionEvidenceArea(
            id="customer_needs",
            label="Customer needs",
            question="What do customers need from the organisation beyond the product?",
            evidence_prompt="Include customer feedback, behaviours or examples.",
            structured_field="stakeholder_insights",
            keywords=["customer", "client", "need", "feedback", "experience"],
        ),
        QuestionEvidenceArea(
            id="employee_experience",
            label="Employee experience",
            question=(
                "What do employees experience when the organisation is working well?"
            ),
            evidence_prompt=(
                "Include signals from staff feedback, retention or decisions."
            ),
            structured_field="stakeholder_insights",
            keywords=["employee", "staff", "team", "people", "culture"],
        ),
        QuestionEvidenceArea(
            id="partner_supplier_context",
            label="Partner and supplier context",
            question="Which partners or suppliers materially shape the organisation?",
            evidence_prompt="Name dependencies, tensions or shared responsibilities.",
            structured_field="stakeholder_insights",
            keywords=["partner", "supplier", "dependency", "investor"],
        ),
        QuestionEvidenceArea(
            id="market_position",
            label="Market position",
            question="How is the organisation positioned against alternatives?",
            evidence_prompt="Compare differentiation, competitors and customer choice.",
            structured_field="positioning_evidence",
            keywords=["position", "market", "competitor", "different", "alternative"],
        ),
        QuestionEvidenceArea(
            id="performance_governance",
            label="Performance and governance",
            question="How does purpose improve focus, decisions or performance?",
            evidence_prompt=(
                "Give examples tied to decisions, governance or efficiency."
            ),
            structured_field="positioning_evidence",
            keywords=["performance", "governance", "decision", "efficiency", "focus"],
        ),
        QuestionEvidenceArea(
            id="social_contribution",
            label="Social contribution",
            question=(
                "What positive contribution does the organisation make for others?"
            ),
            evidence_prompt="Tie contribution to stakeholders, community or outcomes.",
            structured_field="social_contribution_evidence",
            keywords=["impact", "purpose", "community", "social", "contribution"],
        ),
        QuestionEvidenceArea(
            id="people_planet_stakeholders",
            label="People, planet and stakeholders",
            question=(
                "How does the organisation affect people, planet and stakeholders?"
            ),
            evidence_prompt="Use concrete effects, not only intentions.",
            structured_field="social_contribution_evidence",
            keywords=["planet", "stakeholder", "wellbeing", "environment", "people"],
        ),
        QuestionEvidenceArea(
            id="political_context",
            label="Political context",
            question="What political or policy factors shape the organisation?",
            evidence_prompt="Mention policies, public bodies or government priorities.",
            structured_field="pestle_findings",
            keywords=["political", "policy", "government", "public"],
        ),
        QuestionEvidenceArea(
            id="economic_context",
            label="Economic context",
            question="What economic pressures or opportunities matter most?",
            evidence_prompt="Include pricing, funding, cost or market demand signals.",
            structured_field="pestle_findings",
            keywords=["economic", "price", "cost", "funding", "demand"],
        ),
        QuestionEvidenceArea(
            id="social_context",
            label="Social context",
            question="What social expectations or behaviours are changing around you?",
            evidence_prompt="Describe social trends, norms or community expectations.",
            structured_field="pestle_findings",
            keywords=["social", "trend", "expectation", "behaviour", "behavior"],
        ),
        QuestionEvidenceArea(
            id="technology_context",
            label="Technology context",
            question="What technology changes affect the organisation's future?",
            evidence_prompt=(
                "Mention systems, automation, data, AI or digital behaviour."
            ),
            structured_field="pestle_findings",
            keywords=["technology", "digital", "data", "automation", "ai"],
        ),
        QuestionEvidenceArea(
            id="legal_context",
            label="Legal context",
            question="What legal or compliance obligations shape the organisation?",
            evidence_prompt="Name obligations, standards, duties or regulated risks.",
            structured_field="pestle_findings",
            keywords=["legal", "compliance", "standard", "regulation", "duty"],
        ),
        QuestionEvidenceArea(
            id="environmental_context",
            label="Environmental context",
            question="What environmental factors or responsibilities are relevant?",
            evidence_prompt=(
                "Include resource, climate, waste or environmental impacts."
            ),
            structured_field="pestle_findings",
            keywords=["environment", "climate", "waste", "resource", "planet"],
        ),
        QuestionEvidenceArea(
            id="vulnerabilities",
            label="Vulnerabilities",
            question="Where are the current gaps, tensions or vulnerabilities?",
            evidence_prompt="Surface risks, contradictions, weaknesses or unknowns.",
            structured_field="vulnerabilities_gaps",
            keywords=["risk", "gap", "weakness", "vulnerable", "challenge"],
        ),
        QuestionEvidenceArea(
            id="evidence_sources",
            label="Evidence sources",
            question="What evidence should we use to support or challenge this?",
            evidence_prompt="Name reports, surveys, documents, metrics or examples.",
            structured_field="evidence_references",
            keywords=["evidence", "document", "report", "survey", "data"],
        ),
        QuestionEvidenceArea(
            id="open_questions",
            label="Open questions",
            question="What important questions are still unresolved?",
            evidence_prompt=(
                "List the assumptions or decisions that need more evidence."
            ),
            structured_field="open_questions",
            keywords=["unknown", "unresolved", "question", "assumption", "unclear"],
        ),
        QuestionEvidenceArea(
            id="purpose_driven_proof",
            label="Purpose-driven proof",
            question=(
                "What would prove the organisation is purpose-driven, "
                "not just purpose-led?"
            ),
            evidence_prompt="Connect purpose to goals, measures, KPIs or decisions.",
            structured_field="themes",
            keywords=["kpi", "ppi", "measure", "goal", "proof"],
        ),
    ],
    questions=[
        "What does the organisation do, and who does it serve?",
        "What problem does the organisation solve when it is at its best?",
        "What evidence shows how customers, employees or partners experience it today?",
        "Where are the current gaps, tensions or vulnerabilities?",
    ],
)
