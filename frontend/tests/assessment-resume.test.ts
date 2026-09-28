import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  ASSESSMENT_POINTER_KEY,
  getRememberedAssessment,
  isConfirmedUnusableAssessmentStatus,
  rememberAssessment,
  validateRememberedAssessment
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../lib/assessment-pointer.ts";
import {
  assessmentResumePath,
  type ResumableAssessmentSession
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../lib/assessment-resume-path.ts";

const assessmentId = "c892849e-f395-4f36-bae0-769d07a207eb";

class MemoryStorage implements Storage {
  private values = new Map<string, string>();

  get length() {
    return this.values.size;
  }

  clear() {
    this.values.clear();
  }

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  key(index: number) {
    return [...this.values.keys()][index] ?? null;
  }

  removeItem(key: string) {
    this.values.delete(key);
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
  }
}

function session(
  stage: ResumableAssessmentSession["stage"],
  identifyStatus: "not_started" | "in_progress" | "completed" = "in_progress"
): ResumableAssessmentSession {
  return {
    id: assessmentId,
    stage,
    stage_statuses: { identify: identifyStatus }
  };
}

test("a valid remembered assessment remains remembered and resumable", async () => {
  const storage = new MemoryStorage();
  rememberAssessment(assessmentId, storage);

  const result = await validateRememberedAssessment({
    assessmentId,
    loadSession: async () => session("stress_test"),
    resumePath: assessmentResumePath,
    storage
  });

  assert.equal(result?.id, assessmentId);
  assert.equal(getRememberedAssessment(storage), assessmentId);
});

test("stress test resumes at its existing assessment route", () => {
  assert.equal(
    assessmentResumePath(session("stress_test")),
    `/assessments/${assessmentId}/stress-test`
  );
});

test("confirmed 404 and 422 responses are the only clearing statuses", () => {
  assert.equal(isConfirmedUnusableAssessmentStatus(404), true);
  assert.equal(isConfirmedUnusableAssessmentStatus(422), true);
  for (const status of [500, 502, 503]) {
    assert.equal(isConfirmedUnusableAssessmentStatus(status), false);
  }
});

test("a confirmed missing or invalid assessment clears the pointer", async () => {
  for (const status of [404, 422]) {
    const storage = new MemoryStorage();
    rememberAssessment(assessmentId, storage);

    const result = await validateRememberedAssessment({
      assessmentId,
      loadSession: async () =>
        isConfirmedUnusableAssessmentStatus(status) ? null : session("define"),
      resumePath: assessmentResumePath,
      storage
    });

    assert.equal(result, null);
    assert.equal(getRememberedAssessment(storage), null);
  }
});

test("network, server, and parsing failures preserve the pointer", async () => {
  for (const failure of [
    new TypeError("network unavailable"),
    new Error("HTTP 500"),
    new Error("HTTP 503"),
    new Error("response schema mismatch")
  ]) {
    const storage = new MemoryStorage();
    rememberAssessment(assessmentId, storage);

    const result = await validateRememberedAssessment({
      assessmentId,
      loadSession: async () => {
        throw failure;
      },
      resumePath: assessmentResumePath,
      storage
    });

    assert.equal(result, null);
    assert.equal(getRememberedAssessment(storage), assessmentId);
  }
});

test("successful entry can refresh a stale pointer", async () => {
  const storage = new MemoryStorage();
  storage.setItem(ASSESSMENT_POINTER_KEY, "stale-assessment-id");

  await validateRememberedAssessment({
    assessmentId,
    loadSession: async () => session("align"),
    resumePath: assessmentResumePath,
    storage
  });

  assert.equal(getRememberedAssessment(storage), assessmentId);
});

test("existing resume routes remain unchanged", () => {
  assert.equal(
    assessmentResumePath(session("identify")),
    `/assessments/${assessmentId}/identify`
  );
  assert.equal(
    assessmentResumePath(session("identify", "completed")),
    `/assessments/${assessmentId}/identify/brief`
  );
  assert.equal(
    assessmentResumePath(session("define")),
    `/assessments/${assessmentId}/define`
  );
  assert.equal(
    assessmentResumePath(session("align")),
    `/assessments/${assessmentId}/align`
  );
  assert.equal(assessmentResumePath(session("results")), null);
  assert.equal(assessmentResumePath(session("measure")), null);
});

test("the homepage presents Continue after successful validation", () => {
  const source = readFileSync(
    new URL(
      "../components/assessment/StartAssessmentButton.tsx",
      import.meta.url
    ),
    "utf8"
  );

  assert.match(source, /validateRememberedAssessment\(/);
  assert.match(source, /setResumeSession\(session\)/);
  assert.match(source, /resumeSession \? \(/);
  assert.match(source, /Continue assessment/);
});

test("Take the leap starts the new flow without clearing or deleting", () => {
  const source = readFileSync(
    new URL(
      "../components/assessment/StartAssessmentButton.tsx",
      import.meta.url
    ),
    "utf8"
  );

  assert.match(source, /router\.push\("\/identify\/who-are-you"\)/);
  assert.doesNotMatch(source, /clearRememberedAssessment|removeItem|DELETE/);
});

test("assessment routes refresh the pointer through the shared navigation", () => {
  const layoutSource = readFileSync(
    new URL("../app/assessments/[id]/layout.tsx", import.meta.url),
    "utf8"
  );
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

  assert.match(layoutSource, /AssessmentPointerRefresher assessmentId=\{id\}/);
  assert.match(layoutSource, /<AssessmentStageNavigation \/>/);
  assert.match(navigationSource, /useAssessmentSession/);
  assert.match(refresherSource, /validateRememberedAssessment\(/);
  assert.match(refresherSource, /loadSession: getAssessmentSession/);
});
