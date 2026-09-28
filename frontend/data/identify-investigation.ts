export type IdentifyActivitySection = "discover" | "listen" | "understand";

export type IdentifyActivityStatus =
  | "completed"
  | "ai-running"
  | "invite-team"
  | "needs-user"
  | "locked"
  | "conditional"
  | "ready-for-review"
  | "available";

export type MethodologyMappingSupport =
  | "documented-method"
  | "product-ux-interpretation";

export type IdentifyMethodologyMapping = {
  id: string;
  label: string;
  support: MethodologyMappingSupport;
  sourceDocuments: string[];
  sourceNote: string;
};

export type IdentifyActivity = {
  id: string;
  title: string;
  section: IdentifyActivitySection;
  description: string;
  durationMinutes?: number;
  status: IdentifyActivityStatus;
  actionLabel?: string;
  dependencyIds: string[];
  helperText?: string;
  progressLabel?: string | null;
  progress?: {
    current: number;
    total?: number;
    label: string;
  };
  methodologyMapping: IdentifyMethodologyMapping[];
  iconLabel: string;
  accent?: boolean;
};

export type InvestigationSectionData = {
  id: IdentifyActivitySection;
  eyebrow: string;
  title: string;
  completion: string;
  activities: IdentifyActivity[];
};

type InvestigationSectionConfig = {
  id: IdentifyActivitySection;
  eyebrow: string;
  title: string;
  completion: string;
};

export type ConfidenceMetric = {
  label: string;
  value: number;
};

export const statusLabels: Record<IdentifyActivityStatus, string> = {
  completed: "Done",
  "ai-running": "AI running",
  "invite-team": "Invite team",
  "needs-user": "Needs you",
  locked: "Locked",
  conditional: "Conditional",
  "ready-for-review": "Ready for review",
  available: "Available"
};

export const identifyDemoSectionConfig: InvestigationSectionConfig[] = [
  {
    id: "discover",
    eyebrow: "01",
    title: "Discover",
    completion: "0/3"
  },
  {
    id: "listen",
    eyebrow: "02",
    title: "Listen",
    completion: "1/4"
  },
  {
    id: "understand",
    eyebrow: "03",
    title: "Understand",
    completion: "0/5"
  }
];

const methodologySources = {
  technicalArchitecture: "PurpOS_Recommended_Technical_Architecture.docx",
  researchSynthesis: "PurpOS_Neil_Gaught_Research_Synthesis (1).docx"
} as const;

export const identifyDemoActivities: IdentifyActivity[] = [
  {
    id: "ai-detective",
    title: "AI Detective",
    section: "discover",
    description:
      "I read your site, reviews and competitors, then bring you findings to confirm.",
    durationMinutes: 6,
    status: "completed",
    actionLabel: "Review",
    dependencyIds: [],
    methodologyMapping: [
      {
        id: "desk-research",
        label: "Desk research",
        support: "product-ux-interpretation",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify is documented as gathering organisation raw material from business context and optional documents; desk research is the UX interpretation for this activity."
      },
      {
        id: "business-research",
        label: "Business research",
        support: "documented-method",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify inputs include stakeholder/business context and optional uploaded documents."
      },
      {
        id: "competitor-research",
        label: "Competitor research",
        support: "product-ux-interpretation",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Competitor review fits the AI Detective UX, but the inspected docs confirm business context rather than naming competitor research as a formal SOI method step."
      }
    ],
    iconLabel: "Q"
  },
  {
    id: "signal-hunt",
    title: "Signal Hunt",
    section: "discover",
    description:
      "Scanning trends and shifts that could reshape your world in 3 years.",
    durationMinutes: 4,
    status: "ai-running",
    actionLabel: "8 signals ready",
    dependencyIds: ["ai-detective"],
    progress: {
      current: 8,
      label: "signals ready"
    },
    methodologyMapping: [
      {
        id: "trends-analysis",
        label: "Trends analysis",
        support: "product-ux-interpretation",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "The docs confirm PESTLE as Identify input/output; trends analysis is the product wording for exploring external change through that lens."
      },
      {
        id: "pestle",
        label: "PESTLE",
        support: "documented-method",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "Identify is documented as using PESTLE; the research synthesis also identifies the PESTEL tool as part of the consultant playbook."
      }
    ],
    iconLabel: "+",
    accent: true
  },
  {
    id: "discover-synthesis",
    title: "Discover Synthesis",
    section: "discover",
    description:
      "Pull reviewed research and signal decisions into an evidence-backed statement.",
    durationMinutes: 4,
    status: "locked",
    actionLabel: "Review",
    dependencyIds: ["ai-detective", "signal-hunt"],
    methodologyMapping: [
      {
        id: "discover-synthesis",
        label: "Discover evidence synthesis",
        support: "product-ux-interpretation",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify outputs include a discovery brief and themes; this activity synthesizes reviewed Discover evidence toward that output."
      }
    ],
    iconLabel: "S"
  },
  {
    id: "who-matters",
    title: "Who Matters?",
    section: "listen",
    description:
      "Map the people your organisation depends on by influence and importance.",
    durationMinutes: 5,
    status: "completed",
    actionLabel: "Review",
    dependencyIds: [],
    methodologyMapping: [
      {
        id: "stakeholder-mapping",
        label: "Stakeholder mapping",
        support: "documented-method",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify inputs include stakeholder context and outputs include stakeholder insights."
      }
    ],
    iconLabel: "P"
  },
  {
    id: "hot-seat",
    title: "Hot Seat",
    section: "listen",
    description:
      "A 5-min voice interview I run for you - do it yourself, or send it to your people.",
    durationMinutes: 7,
    status: "invite-team",
    actionLabel: "Set up",
    dependencyIds: ["who-matters"],
    methodologyMapping: [
      {
        id: "guided-sme-founder-interview",
        label: "Guided SME/founder interview",
        support: "documented-method",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "The docs confirm guided CORE/SOI questions and an interview section containing questions companies can ask of themselves."
      }
    ],
    iconLabel: "M"
  },
  {
    id: "company-cards",
    title: "Company Cards",
    section: "listen",
    description:
      "Pick the images that feel like your company - today, and who you want to become.",
    durationMinutes: 5,
    status: "needs-user",
    actionLabel: "Start",
    dependencyIds: [],
    methodologyMapping: [
      {
        id: "organisational-identity-perception-elicitation",
        label: "Organisational identity/perception elicitation",
        support: "product-ux-interpretation",
        sourceDocuments: [methodologySources.researchSynthesis],
        sourceNote:
          "The research synthesis discusses identity and positioning concerns; the card-based visual elicitation mechanic is a UX interpretation, not an explicitly confirmed SOI method step in the inspected docs."
      }
    ],
    iconLabel: "C"
  },
  {
    id: "listen-summary",
    title: "Listen Summary",
    section: "listen",
    description:
      "Pull stakeholder, interview and metaphor evidence into a short Listen readout.",
    durationMinutes: 3,
    status: "locked",
    actionLabel: "Review",
    dependencyIds: ["who-matters", "hot-seat", "company-cards"],
    methodologyMapping: [
      {
        id: "listen-synthesis",
        label: "Listen evidence synthesis",
        support: "product-ux-interpretation",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify outputs include stakeholder insights, evidence references and open questions; this activity summarizes evidence gathered across the Listen lane."
      }
    ],
    iconLabel: "L"
  },
  {
    id: "day-in-their-shoes",
    title: "A Day in Their Shoes",
    section: "understand",
    description:
      "Walk a stakeholder's journey and mark the moments that matter.",
    status: "locked",
    dependencyIds: ["who-matters"],
    helperText: "Unlocks after Who Matters?",
    methodologyMapping: [
      {
        id: "stakeholder-touchpoint-journey",
        label: "Stakeholder/touchpoint journey",
        support: "product-ux-interpretation",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Stakeholder context and insights are documented Identify material; journey/touchpoint framing is the UX mapping for exploring stakeholder experience."
      }
    ],
    iconLabel: "J"
  },
  {
    id: "where-do-you-stand",
    title: "Where Do You Stand",
    section: "understand",
    description:
      "Place yourself on positioning and social contribution - today vs. tomorrow.",
    durationMinutes: 6,
    status: "available",
    actionLabel: "Start",
    dependencyIds: [],
    methodologyMapping: [
      {
        id: "positioning",
        label: "Positioning exploration",
        support: "documented-method",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "Identify outputs include positioning evidence, and Define outputs include a positioning statement."
      },
      {
        id: "social-contribution",
        label: "Social-contribution exploration",
        support: "documented-method",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify outputs include social contribution evidence."
      }
    ],
    iconLabel: "B"
  },
  {
    id: "perception-gaps",
    title: "Perception Gaps",
    section: "understand",
    description:
      "Where what you say meets what people feel. I'll surface these when I have enough.",
    status: "conditional",
    dependencyIds: ["hot-seat", "company-cards"],
    helperText: "Needs 2+ evidence sources - 1 so far",
    progress: {
      current: 1,
      total: 2,
      label: "evidence sources"
    },
    methodologyMapping: [
      {
        id: "evidence-source-comparison",
        label: "Comparison across evidence sources",
        support: "documented-method",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Cross-checking against earlier evidence and uploaded evidence is documented as a first-class architecture behaviour."
      },
      {
        id: "perspective-comparison",
        label: "Comparison across perspectives",
        support: "product-ux-interpretation",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "The docs distinguish founder, stakeholder and SME evidence needs; treating that as perspective comparison is a UX interpretation."
      }
    ],
    iconLabel: "<>",
    accent: true
  },
  {
    id: "evidence-wall",
    title: "Evidence Wall",
    section: "understand",
    description:
      "The boss level - all your evidence on one wall, clustered into themes.",
    status: "locked",
    dependencyIds: ["perception-gaps"],
    helperText: "Unlocks when Identify evidence exists",
    methodologyMapping: [
      {
        id: "evidence-synthesis",
        label: "Evidence synthesis",
        support: "documented-method",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "Identify outputs include themes, and the research synthesis frames the work as evidence-traced synthesis."
      },
      {
        id: "themes",
        label: "Themes",
        support: "documented-method",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote: "Identify outputs explicitly include themes."
      },
      {
        id: "triangulation",
        label: "Triangulation",
        support: "product-ux-interpretation",
        sourceDocuments: [
          methodologySources.technicalArchitecture,
          methodologySources.researchSynthesis
        ],
        sourceNote:
          "The docs support comparing evidence sources; triangulation is the product interpretation for the Evidence Wall synthesis experience."
      }
    ],
    iconLabel: "E"
  },
  {
    id: "identify-brief",
    title: "Identify Brief",
    section: "understand",
    description:
      "The final Identify handoff pack for Define - evidence, themes, tensions and open questions.",
    durationMinutes: 3,
    status: "locked",
    actionLabel: "Review",
    dependencyIds: ["evidence-wall"],
    helperText: "Unlocks when the Evidence Wall has a saved theme",
    methodologyMapping: [
      {
        id: "identify-handoff",
        label: "Identify to Define handoff",
        support: "documented-method",
        sourceDocuments: [methodologySources.technicalArchitecture],
        sourceNote:
          "Identify outputs feed Define with evidence, themes, positioning and unresolved questions; the brief packages that handoff without writing the final purpose statement."
      }
    ],
    iconLabel: "I",
    accent: true
  }
];

export const identifyDemoInvestigationSections: InvestigationSectionData[] =
  identifyDemoSectionConfig.map((section) => ({
    ...section,
    activities: identifyDemoActivities.filter(
      (activity) => activity.section === section.id
    )
  }));

export const identifyDemoConfidenceMetrics: ConfidenceMetric[] = [
  { label: "Core Purpose", value: 20 },
  { label: "Values", value: 15 },
  { label: "Positioning", value: 60 },
  { label: "Networks", value: 55 },
  { label: "Success Indicators", value: 45 },
  { label: "Strategic Implementation", value: 25 }
];

export const identifyDemoSummary = {
  completed: 4,
  total: 9,
  confidence: 38,
  confidenceCaption: "confident across 6 areas",
  biggestGapTitle: "I know almost nothing about what your people think.",
  biggestGapDescription:
    "Invite 3 employees for a 5-min Hot Seat and I'll interview them for you."
};
