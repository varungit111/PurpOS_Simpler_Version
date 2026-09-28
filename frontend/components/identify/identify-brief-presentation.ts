type BriefEvidenceText = {
  claim: string;
  summary: string | null;
  sourceActivity: string | null;
};

const questionLabels: Record<string, string> = {
  discovery_brief: "What additional context is needed to complete the discovery brief?",
  themes: "Which emerging themes still need stronger evidence or clarification?",
  pestle_findings: "Which PESTLE factors still need stronger evidence or clarification?",
  stakeholder_insights: "Which stakeholder perspectives still need stronger evidence?",
  positioning_evidence:
    "What stronger evidence is needed to clarify the organisation's positioning?",
  social_contribution_evidence:
    "What stronger evidence can demonstrate the organisation's social contribution?",
  vulnerabilities_gaps: "Which vulnerabilities or unresolved risks need further investigation?",
  open_questions: "Which important questions still need clarification?",
  evidence_references: "Which important claims still need stronger supporting evidence?"
};

export function formatIdentifyBriefQuestion(question: string) {
  return questionLabels[question.trim()] ?? question;
}

export function formatIdentifyBriefEvidenceClaim(item: BriefEvidenceText) {
  const summary = item.summary?.trim();
  if (item.sourceActivity !== "day-in-their-shoes" || !summary) {
    return item.claim;
  }

  const escapedSummary = summary.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const repeatedSummary = new RegExp(`(${escapedSummary})(?:\\s+\\1)+`, "gi");
  return item.claim.replace(repeatedSummary, "$1");
}
