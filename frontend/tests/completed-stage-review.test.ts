import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  isStageReviewOnly,
  type ReviewModeSession
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../lib/assessment-review-mode.ts";

const stressTestSession: ReviewModeSession = {
  stage: "stress_test",
  stage_statuses: {
    identify: "completed",
    define: "completed",
    stress_test: "in_progress",
    align: "not_started"
  }
};

test("active Identify remains editable", () => {
  assert.equal(
    isStageReviewOnly(
      {
        stage: "identify",
        stage_statuses: { identify: "in_progress" }
      },
      "identify"
    ),
    false
  );
});

test("completed earlier stages use review mode", () => {
  assert.equal(isStageReviewOnly(stressTestSession, "identify"), true);
  assert.equal(isStageReviewOnly(stressTestSession, "define"), true);
});

test("Define review replaces completion with a Stress Test return link", () => {
  const source = readFileSync(
    new URL("../components/define/DefineReview.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /reviewOnly \?/);
  assert.match(source, /session\?\.stage === "stress_test"/);
  assert.match(source, /Return to Stress Test/);
  assert.match(source, /\/stress-test/);
});

test("Positioning reads persisted Define state in review mode", () => {
  const source = readFileSync(
    new URL("../components/define/PositioningEditor.tsx", import.meta.url),
    "utf8"
  );

  assert.match(source, /reviewOnly \? getDefine : generateDefine/);
});

test("review boundaries preserve navigation and suppress mutations", () => {
  const source = readFileSync(
    new URL(
      "../components/assessment/CompletedStageReviewBoundary.tsx",
      import.meta.url
    ),
    "utf8"
  );

  assert.match(source, /data-stage-mutation/);
  assert.match(source, /onSubmitCapture/);
  assert.match(source, /Completed - review only/);
  assert.doesNotMatch(source, /router\.(push|replace)|fetch\(/);
});
