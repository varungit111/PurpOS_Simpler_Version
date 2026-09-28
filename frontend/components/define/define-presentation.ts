export function splitSoiStatement(statement: string) {
  const words = statement.trim().split(/\s+/).filter(Boolean);
  if (words.length < 2) return { lead: words.join(" "), accent: "" };
  return {
    lead: words.slice(0, -1).join(" "),
    accent: words.at(-1) ?? ""
  };
}

export function organisationDisplayName(companyName: string | null | undefined) {
  return companyName?.trim() || "This organisation";
}

export function valueChainHeading(statement: string | null | undefined) {
  return statement?.trim() || "Value Chain - Moments of Truth";
}

export function composePositioningStatement(
  organisationName: string,
  positioning: {
    audience: string | null;
    categoryContext: string | null;
    capabilityValue: string | null;
    reasonBelievability: string | null;
  }
) {
  const { audience, categoryContext, capabilityValue, reasonBelievability } = positioning;
  if (!audience?.trim() || !categoryContext?.trim() || !capabilityValue?.trim() || !reasonBelievability?.trim()) return "";
  return `For ${audience}, ${organisationDisplayName(organisationName)} is the ${categoryContext} that ${capabilityValue} - because ${reasonBelievability}`;
}
