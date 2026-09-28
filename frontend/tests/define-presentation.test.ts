import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  composePositioningStatement,
  organisationDisplayName,
  splitSoiStatement,
  valueChainHeading
  // @ts-expect-error Node's type-stripping test runner requires the .ts extension.
} from "../components/define/define-presentation.ts";

test("splits the persisted SOI without replacing its content", () => {
  assert.deepEqual(splitSoiStatement("Employee experience"), {
    lead: "Employee",
    accent: "experience"
  });
  assert.deepEqual(splitSoiStatement("Belong"), {
    lead: "Belong",
    accent: ""
  });
});

test("uses the current assessment organisation in positioning", () => {
  assert.equal(organisationDisplayName("Meridian"), "Meridian");
  assert.equal(organisationDisplayName("  North Star  "), "North Star");
  assert.equal(organisationDisplayName(null), "This organisation");
});

test("uses the current assessment SOI as the value-chain heading", () => {
  assert.equal(valueChainHeading("Employee experience"), "Employee experience");
  assert.equal(valueChainHeading(null), "Value Chain - Moments of Truth");
});

test("composes positioning from all four editable slots", () => {
  assert.equal(
    composePositioningStatement("Meridian", {
      audience: "clinic managers",
      categoryContext: "operations partner",
      capabilityValue: "keeps care workflows reliable",
      reasonBelievability: "customers need daily confidence"
    }),
    "For clinic managers, Meridian is the operations partner that keeps care workflows reliable - because customers need daily confidence"
  );
  assert.equal(
    composePositioningStatement("Meridian", {
      audience: "clinic managers",
      categoryContext: null,
      capabilityValue: "keeps care workflows reliable",
      reasonBelievability: "customers need daily confidence"
    }),
    ""
  );
});

test("live Define components do not contain supplied sample content", () => {
  const componentPaths = [
    "DefineReveal.tsx",
    "PositioningEditor.tsx",
    "ValuesEditor.tsx",
    "ValueChainOverview.tsx",
    "MomentDetail.tsx"
  ];
  const source = componentPaths
    .map((name) => readFileSync(new URL(`../components/define/${name}`, import.meta.url), "utf8"))
    .join("\n");

  assert.doesNotMatch(source, /GROUND UP/i);
  assert.doesNotMatch(source, /Hawkins/i);
  assert.doesNotMatch(source, /Business as a force for good/i);
  assert.doesNotMatch(source, /\bRooted\b/i);
});

test("Positioning loads safely and saves through assessment-scoped API paths", () => {
  const source = readFileSync(
    new URL("../components/define/PositioningEditor.tsx", import.meta.url),
    "utf8"
  );
  assert.match(source, /reviewOnly \? getDefine : generateDefine/);
  assert.match(source, /loadDefine\(assessmentId\)/);
  assert.match(source, /updateDefinePositioning\(assessmentId/);
  for (const field of [
    "audience",
    "categoryContext",
    "capabilityValue",
    "reasonBelievability"
  ]) {
    assert.match(source, new RegExp(`updateField\\(\\"${field}\\"`));
  }
  assert.match(
    source,
    /router\.push\(`\/assessments\/\$\{assessmentId\}\/define\/values`\)/
  );
});
