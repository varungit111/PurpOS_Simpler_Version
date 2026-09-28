import assert from "node:assert/strict";
import test from "node:test";

import {
  formatIdentifyBriefEvidenceClaim,
  formatIdentifyBriefQuestion
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../components/identify/identify-brief-presentation.ts";

test("maps internal Identify output keys to user-facing evidence needs", () => {
  const expected = new Map([
    [
      "pestle_findings",
      "Which PESTLE factors still need stronger evidence or clarification?"
    ],
    [
      "social_contribution_evidence",
      "What stronger evidence can demonstrate the organisation's social contribution?"
    ],
    [
      "vulnerabilities_gaps",
      "Which vulnerabilities or unresolved risks need further investigation?"
    ],
    [
      "evidence_references",
      "Which important claims still need stronger supporting evidence?"
    ]
  ]);

  for (const [key, label] of expected) {
    assert.equal(formatIdentifyBriefQuestion(key), label);
    assert.doesNotMatch(formatIdentifyBriefQuestion(key), /^[a-z]+(?:_[a-z]+)+$/);
  }
});

test("preserves genuine user-authored open questions", () => {
  const question = "Which customer claim still needs validation?";
  assert.equal(formatIdentifyBriefQuestion(question), question);
});

test("removes only repeated journey summaries from displayed evidence", () => {
  const claim = "Customers Getting a quote Getting a quote should feel reliable.";
  assert.equal(
    formatIdentifyBriefEvidenceClaim({
      claim,
      summary: "Getting a quote",
      sourceActivity: "day-in-their-shoes"
    }),
    "Customers Getting a quote should feel reliable."
  );
  assert.equal(
    formatIdentifyBriefEvidenceClaim({
      claim,
      summary: "Getting a quote",
      sourceActivity: "signal-hunt"
    }),
    claim
  );
});
