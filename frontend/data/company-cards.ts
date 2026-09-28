export type CompanyCardTone =
  | "violet"
  | "blue"
  | "green"
  | "amber"
  | "rose"
  | "slate";

export type CompanyCardDefinition = {
  id: string;
  title: string;
  cue: string;
  quality: string;
  tone: CompanyCardTone;
};

export const companyCardDeckVersion = "prototype-2026-09";

export const companyCardContentStatus =
  "Prototype UX content based on the playbook's Today and Tomorrow workshop exercise.";

export const companyCardDefinitions: CompanyCardDefinition[] = [
  {
    id: "steady-compass",
    title: "Steady Compass",
    cue: "Clear direction",
    quality: "Focused",
    tone: "violet"
  },
  {
    id: "open-door",
    title: "Open Door",
    cue: "Easy to approach",
    quality: "Accessible",
    tone: "green"
  },
  {
    id: "precision-tool",
    title: "Precision Tool",
    cue: "Sharp execution",
    quality: "Reliable",
    tone: "blue"
  },
  {
    id: "spark-board",
    title: "Spark Board",
    cue: "New ideas",
    quality: "Inventive",
    tone: "amber"
  },
  {
    id: "strong-bridge",
    title: "Strong Bridge",
    cue: "Connection across groups",
    quality: "Collaborative",
    tone: "slate"
  },
  {
    id: "signal-tower",
    title: "Signal Tower",
    cue: "Visible and trusted",
    quality: "Credible",
    tone: "rose"
  },
  {
    id: "workbench",
    title: "Workbench",
    cue: "Practical problem solving",
    quality: "Useful",
    tone: "green"
  },
  {
    id: "springboard",
    title: "Springboard",
    cue: "Momentum for growth",
    quality: "Ambitious",
    tone: "amber"
  },
  {
    id: "woven-network",
    title: "Woven Network",
    cue: "Many relationships working together",
    quality: "Connected",
    tone: "violet"
  },
  {
    id: "clear-window",
    title: "Clear Window",
    cue: "Transparent choices",
    quality: "Honest",
    tone: "blue"
  },
  {
    id: "solid-foundation",
    title: "Solid Foundation",
    cue: "Built to last",
    quality: "Resilient",
    tone: "slate"
  },
  {
    id: "human-circle",
    title: "Human Circle",
    cue: "People at the centre",
    quality: "Human",
    tone: "rose"
  }
];
