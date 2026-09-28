export type IdentifyDependencyContext = {
  evidenceSourceCount: number;
  stakeholderCount: number;
};

export type IdentifyDependencyRule = {
  activityId: string;
  requiredActivityId: string;
  lockedMessage: string;
  isSatisfied: (context: IdentifyDependencyContext) => boolean;
};

export const dayInTheirShoesDependency: IdentifyDependencyRule = {
  activityId: "day-in-their-shoes",
  requiredActivityId: "who-matters",
  lockedMessage:
    "Add at least one stakeholder in Who Matters? before mapping journeys.",
  isSatisfied: (context) => context.stakeholderCount > 0
};

export const perceptionGapsDependency: IdentifyDependencyRule = {
  activityId: "perception-gaps",
  requiredActivityId: "meaningful-identify-evidence",
  lockedMessage:
    "Perception Gaps needs at least two meaningful Identify evidence sources.",
  isSatisfied: (context) => context.evidenceSourceCount >= 2
};
