export type PositioningEvidenceTopic =
  | "who-served"
  | "value-created"
  | "current-positioning"
  | "distinctiveness"
  | "social-contribution"
  | "current-vs-desired";

export type PositioningPrompt = {
  id: PositioningEvidenceTopic;
  label: string;
  prompt: string;
  helper: string;
};

export const positioningPrompts: PositioningPrompt[] = [
  {
    id: "who-served",
    label: "Who you serve",
    prompt: "Who does the organisation primarily serve?",
    helper:
      "Name the stakeholder groups this organisation exists to help or depend on."
  },
  {
    id: "value-created",
    label: "Value created",
    prompt: "What value does the organisation create for them?",
    helper: "Capture practical, emotional, commercial or wider value."
  },
  {
    id: "current-positioning",
    label: "Current position",
    prompt: "How is the organisation positioned today?",
    helper: "Think proposition, messages, qualities, tone and what people remember."
  },
  {
    id: "distinctiveness",
    label: "Distinctiveness",
    prompt: "What feels distinctive compared with alternatives?",
    helper: "Focus on what is meaningfully different, not a finished statement."
  },
  {
    id: "social-contribution",
    label: "Wider contribution",
    prompt: "What wider contribution is already visible?",
    helper:
      "Include social, environmental, community or stakeholder value where evidenced."
  },
  {
    id: "current-vs-desired",
    label: "Today vs future",
    prompt: "What needs to shift between the current and desired position?",
    helper: "Capture the gap that Define should later synthesize."
  }
];
