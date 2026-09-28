import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  agreementActionsDisabled,
  beginAgreement,
  clearAgreementError,
  endAgreement,
  replaceCriterion,
  setAgreementError
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../components/stress-test/stress-test-review-state.ts";

test("one pending agreement locks every criterion action", () => {
  const lock = { current: null as string | null };

  assert.equal(beginAgreement(lock, "credible"), true);
  assert.equal(agreementActionsDisabled(lock.current), true);
  assert.equal(beginAgreement(lock, "commercial"), false);
  assert.equal(lock.current, "credible");

  endAgreement(lock, "credible");
  assert.equal(agreementActionsDisabled(lock.current), false);
});

test("reviewed state changes only when the authoritative criterion is applied", () => {
  const criteria = [
    { criterionId: "credible", approvalStatus: "agreed" },
    { criterionId: "commercial", approvalStatus: "ai-proposed" }
  ];

  assert.equal(criteria[1].approvalStatus, "ai-proposed");
  const saved = { criterionId: "commercial", approvalStatus: "agreed" };
  const updated = replaceCriterion(criteria, saved);

  assert.equal(updated[1].approvalStatus, "agreed");
  assert.equal(updated[0].approvalStatus, "agreed");
  assert.equal(criteria[1].approvalStatus, "ai-proposed");
});

test("a failed agreement remains visible until that criterion succeeds", () => {
  let errors = setAgreementError({}, "commercial", "Version conflict");

  errors = clearAgreementError(errors, "credible");
  assert.equal(errors.commercial, "Version conflict");

  errors = setAgreementError(errors, "resilient", "Network unavailable");
  errors = clearAgreementError(errors, "resilient");
  assert.equal(errors.commercial, "Version conflict");

  errors = clearAgreementError(errors, "commercial");
  assert.deepEqual(errors, {});
});

test("a failed criterion can be retried after its request releases the lock", () => {
  const lock = { current: null as string | null };
  assert.equal(beginAgreement(lock, "commercial"), true);
  endAgreement(lock, "commercial");
  assert.equal(beginAgreement(lock, "commercial"), true);
});

test("the review UI wires the global lock and criterion-specific errors to every card", () => {
  const source = readFileSync(
    new URL(
      "../components/stress-test/StressTestReview.tsx",
      import.meta.url
    ),
    "utf8"
  );

  assert.match(
    source,
    /disabled=\{busy !== null \|\| agreementActionsDisabled\(agreementLock\.current\)\}/
  );
  assert.match(source, /error=\{criterionErrors\[item\.criterionId\] \?\? null\}/);
  assert.match(source, /item\.approvalStatus === "agreed" \? "Reviewed"/);
  assert.match(source, /role="alert">Could not save \{item\.name\}/);
});
