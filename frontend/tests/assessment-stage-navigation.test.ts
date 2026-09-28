import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  buildAssessmentStageNavigation,
  type AssessmentStageNavigationSession
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../lib/assessment-stage-navigation.ts";

const assessmentId = "c892849e-f395-4f36-bae0-769d07a207eb";

function stressTestSession(): AssessmentStageNavigationSession {
  return {
    id: assessmentId,
    stage: "stress_test",
    stage_statuses: {
      identify: "completed",
      define: "completed",
      stress_test: "in_progress",
      align: "not_started"
    }
  };
}

test("completed stages are clickable review destinations", () => {
  const stages = buildAssessmentStageNavigation(stressTestSession());
  const identify = stages.find((stage) => stage.id === "identify");
  const define = stages.find((stage) => stage.id === "define");

  assert.deepEqual(
    { state: identify?.state, href: identify?.href },
    {
      state: "completed",
      href: `/assessments/${assessmentId}/identify`
    }
  );
  assert.deepEqual(
    { state: define?.state, href: define?.href },
    {
      state: "completed",
      href: `/assessments/${assessmentId}/define/review`
    }
  );
});

test("the backend current stage controls the current marker and route", () => {
  const stressTest = buildAssessmentStageNavigation(stressTestSession()).find(
    (stage) => stage.id === "stress_test"
  );

  assert.deepEqual(
    { state: stressTest?.state, href: stressTest?.href },
    {
      state: "current",
      href: `/assessments/${assessmentId}/stress-test`
    }
  );
});

test("future and unimplemented stages are disabled", () => {
  const stages = buildAssessmentStageNavigation(stressTestSession());

  for (const id of ["align", "measure"] as const) {
    const stage = stages.find((item) => item.id === id);
    assert.equal(stage?.state, "disabled");
    assert.equal(stage?.href, null);
  }
});

test("Align becomes accessible only when it is current or completed", () => {
  const session = stressTestSession();
  session.stage = "align";
  session.stage_statuses.stress_test = "completed";
  session.stage_statuses.align = "in_progress";

  const align = buildAssessmentStageNavigation(session).find(
    (stage) => stage.id === "align"
  );

  assert.equal(align?.state, "current");
  assert.equal(align?.href, `/assessments/${assessmentId}/align`);
});

test("building navigation does not mutate workflow state", () => {
  const session = stressTestSession();
  const before = structuredClone(session);

  buildAssessmentStageNavigation(session);

  assert.deepEqual(session, before);
});

test("the shared navigation only loads session state and renders links", () => {
  const navigationSource = readFileSync(
    new URL(
      "../components/assessment/AssessmentStageNavigation.tsx",
      import.meta.url
    ),
    "utf8"
  );
  const refresherSource = readFileSync(
    new URL(
      "../components/assessment/AssessmentPointerRefresher.tsx",
      import.meta.url
    ),
    "utf8"
  );

  assert.match(refresherSource, /loadSession: getAssessmentSession/);
  assert.match(navigationSource, /useAssessmentSession/);
  assert.doesNotMatch(
    `${navigationSource}\n${refresherSource}`,
    /completeStressTest|generateAlignment|generateDefine|completeDefine|updateDefine|method:\s*["'](?:POST|PATCH|PUT|DELETE)/
  );
});
