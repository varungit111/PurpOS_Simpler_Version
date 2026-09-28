"use client";

import type { Stakeholder } from "@/lib/stakeholders";
import { getStakeholders, saveStakeholders } from "@/lib/stakeholders";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type WhoMattersMapProps = {
  assessmentId: string;
};

type FormState = {
  name: string;
  groupType: Stakeholder["groupType"];
  internalOrExternal: Stakeholder["internalOrExternal"];
  relationship: string;
  importance: Stakeholder["importance"];
  influence: Stakeholder["influence"];
  needs: string;
  expectations: string;
  notes: string;
  evidenceSource: string;
};

const emptyForm: FormState = {
  name: "",
  groupType: "customer",
  internalOrExternal: "external",
  relationship: "",
  importance: "medium",
  influence: "medium",
  needs: "",
  expectations: "",
  notes: "",
  evidenceSource: "Who Matters?"
};

const groupTypes: Stakeholder["groupType"][] = [
  "customer",
  "employee",
  "supplier",
  "partner",
  "owner",
  "investor",
  "community",
  "regulator",
  "other"
];

const levels: Stakeholder["importance"][] = ["low", "medium", "high"];

export function WhoMattersMap({ assessmentId }: WhoMattersMapProps) {
  const [stakeholders, setStakeholders] = useState<Stakeholder[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    getStakeholders(assessmentId)
      .then((loadedStakeholders) => {
        if (isMounted) {
          setStakeholders(loadedStakeholders);
          setError(null);
        }
      })
      .catch(() => {
        if (isMounted) {
          setError("I couldn't load the stakeholder map.");
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [assessmentId]);

  const completenessLabel = useMemo(() => {
    const count = stakeholders.length;
    if (count === 0) {
      return "No stakeholders mapped yet";
    }
    return `${count} stakeholder${count === 1 ? "" : "s"} mapped`;
  }, [stakeholders.length]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const stakeholder = stakeholderFromForm(form, editingId);
    setStakeholders((current) => {
      if (!editingId) {
        return [...current, stakeholder];
      }
      return current.map((item) => (item.id === editingId ? stakeholder : item));
    });
    setForm(emptyForm);
    setEditingId(null);
    setStatus(null);
  }

  function handleEdit(stakeholder: Stakeholder) {
    setEditingId(stakeholder.id);
    setForm({
      name: stakeholder.name,
      groupType: stakeholder.groupType,
      internalOrExternal: stakeholder.internalOrExternal,
      relationship: stakeholder.relationship ?? "",
      importance: stakeholder.importance,
      influence: stakeholder.influence,
      needs: stakeholder.needs.join(", "),
      expectations: stakeholder.expectations.join(", "),
      notes: stakeholder.notes ?? "",
      evidenceSource: stakeholder.evidenceSource
    });
  }

  function handleRemove(stakeholderId: string) {
    setStakeholders((current) =>
      current.filter((stakeholder) => stakeholder.id !== stakeholderId)
    );
    if (editingId === stakeholderId) {
      setEditingId(null);
      setForm(emptyForm);
    }
    setStatus(null);
  }

  async function handleSave() {
    setIsSaving(true);
    setError(null);
    setStatus(null);

    try {
      const savedStakeholders = await saveStakeholders({
        sessionId: assessmentId,
        stakeholders
      });
      setStakeholders(savedStakeholders);
      setStatus("Stakeholder map saved to the Identify session.");
    } catch {
      setError("I couldn't save the stakeholder map.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f2f2f4] text-[#292735]">
      <header className="border-b border-slate-200 bg-white">
        <nav className="flex min-h-16 items-center justify-between gap-4 px-5 sm:px-8">
          <Link
            className="flex items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
            href={`/assessments/${assessmentId}/identify`}
          >
            <span className="grid size-8 place-items-center rounded-md bg-[#6f50b5] text-sm font-bold text-white">
              P
            </span>
            <span className="text-base font-bold">PurpOS</span>
          </Link>
          <div className="hidden items-center gap-4 text-sm sm:flex">
            <span className="font-semibold tracking-[0.18em] text-slate-500">
              IDENTIFY
            </span>
            <span className="text-slate-400">01 Discover</span>
            <span className="font-semibold text-[#6f50b5]">02 Listen</span>
            <span className="text-slate-400">03 Understand</span>
          </div>
          <Link
            className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-[#292735] outline-none transition hover:border-[#6f50b5] hover:text-[#6f50b5] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
            href={`/assessments/${assessmentId}/identify`}
          >
            Board
          </Link>
        </nav>
      </header>

      <main className="px-5 py-7 sm:px-8">
        <section className="mx-auto max-w-7xl">
          <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
            02 Listen - Who Matters?
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-normal">
            Who does your organisation actually depend on?
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Place each group by influence and importance, then save the map as
            Listen evidence.
          </p>
        </section>

        <section className="mx-auto mt-6 grid max-w-7xl gap-5 xl:grid-cols-[minmax(0,1fr)_410px]">
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <StakeholderPlot
              onEdit={handleEdit}
              stakeholders={stakeholders}
            />

            <div className="mt-5 rounded-md border border-[#c9b9ef] bg-[#eee6fb] p-4">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-sm font-bold">
                    {stakeholders.length > 0
                      ? `You lean on ${stakeholders.length} group${
                          stakeholders.length === 1 ? "" : "s"
                        } - ${stakeholders
                          .filter((item) => item.importance === "high")
                          .slice(0, 3)
                          .map((item) => item.name)
                          .join(", ") || "keep mapping the critical few"}.`
                      : "Start by adding the groups your organisation depends on."}
                  </p>
                  <p className="mt-1 text-sm text-slate-600">
                    Save the map before inviting people into Hot Seat.
                  </p>
                </div>
                <Link
                  className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#6f50b5] px-5 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                  href={`/assessments/${assessmentId}/identify/hot-seat`}
                >
                  Invite them to Hot Seat <span className="ml-2">-&gt;</span>
                </Link>
              </div>
            </div>
          </div>

          <aside className="grid gap-5">
            <section className="rounded-lg border border-[#c9b9ef] bg-[#eee6fb] p-5">
              <p className="text-xs font-bold uppercase tracking-[0.24em] text-[#6f50b5]">
                I&apos;ll throw you a few wildcards
              </p>
              <div className="mt-4 grid gap-2">
                {["Former employees", "The families of your customers", "The local environment"].map(
                  (name) => (
                    <button
                      className="rounded-md border border-dashed border-[#6f50b5]/30 bg-white px-3 py-3 text-left text-sm font-semibold outline-none transition hover:border-[#6f50b5]"
                      key={name}
                      onClick={() =>
                        setForm({
                          ...emptyForm,
                          name,
                          groupType:
                            name === "The local environment"
                              ? "community"
                              : "other",
                          influence: "medium",
                          importance: "medium"
                        })
                      }
                      type="button"
                    >
                      + {name}
                    </button>
                  )
                )}
              </div>
              <p className="mt-4 text-sm text-slate-600">
                {completenessLabel} - drag-style placement is captured through
                influence and importance.
              </p>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-500">
                  Add or edit
                </p>
                <button
                  className="rounded-md bg-[#6f50b5] px-4 py-2 text-sm font-bold text-white outline-none transition hover:bg-[#6043a2] disabled:cursor-not-allowed disabled:bg-slate-300 focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                  disabled={isSaving || isLoading}
                  data-stage-mutation
                  onClick={handleSave}
                  type="button"
                >
                  {isSaving ? "Saving..." : "Save map"}
                </button>
              </div>

              {error ? (
                <p className="mt-4 text-sm font-medium text-red-700" role="alert">
                  {error}
                </p>
              ) : null}
              {status ? (
                <p className="mt-4 text-sm font-medium text-[#6f50b5]">
                  {status}
                </p>
              ) : null}

              <form className="mt-5 grid gap-4" onSubmit={handleSubmit}>
                <TextField
                  label="Name"
                  onChange={(value) => setForm({ ...form, name: value })}
                  required
                  value={form.name}
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <SelectField
                    label="Group"
                    onChange={(value) =>
                      setForm({
                        ...form,
                        groupType: value as FormState["groupType"]
                      })
                    }
                    options={groupTypes}
                    value={form.groupType}
                  />
                  <SelectField
                    label="Position"
                    onChange={(value) =>
                      setForm({
                        ...form,
                        internalOrExternal:
                          value as FormState["internalOrExternal"]
                      })
                    }
                    options={["internal", "external", "both"]}
                    value={form.internalOrExternal}
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <SelectField
                    label="Influence"
                    onChange={(value) =>
                      setForm({
                        ...form,
                        influence: value as FormState["influence"]
                      })
                    }
                    options={levels}
                    value={form.influence}
                  />
                  <SelectField
                    label="Importance"
                    onChange={(value) =>
                      setForm({
                        ...form,
                        importance: value as FormState["importance"]
                      })
                    }
                    options={levels}
                    value={form.importance}
                  />
                </div>
                <TextField
                  label="Relationship"
                  onChange={(value) => setForm({ ...form, relationship: value })}
                  value={form.relationship}
                />
                <TextField
                  label="Needs"
                  onChange={(value) => setForm({ ...form, needs: value })}
                  value={form.needs}
                />
                <TextArea
                  label="Notes"
                  onChange={(value) => setForm({ ...form, notes: value })}
                  value={form.notes}
                />
                <TextField
                  label="Evidence source"
                  onChange={(value) =>
                    setForm({ ...form, evidenceSource: value })
                  }
                  required
                  value={form.evidenceSource}
                />
                <button
                  className="inline-flex min-h-11 items-center justify-center rounded-md bg-[#6f50b5] px-5 text-sm font-bold text-white shadow-sm outline-none transition hover:bg-[#6043a2] focus-visible:ring-2 focus-visible:ring-[#6f50b5] focus-visible:ring-offset-2"
                  type="submit"
                >
                  {editingId ? "Update stakeholder" : "Add stakeholder"}
                </button>
                {editingId ? (
                  <button
                    className="inline-flex min-h-11 items-center justify-center rounded-md border border-red-200 bg-white px-5 text-sm font-bold text-red-700 outline-none transition hover:border-red-400 focus-visible:ring-2 focus-visible:ring-red-300 focus-visible:ring-offset-2"
                    onClick={() => handleRemove(editingId)}
                    type="button"
                  >
                    Remove stakeholder
                  </button>
                ) : null}
              </form>
            </section>
          </aside>
        </section>
      </main>
    </div>
  );
}

function StakeholderPlot({
  onEdit,
  stakeholders
}: {
  onEdit: (stakeholder: Stakeholder) => void;
  stakeholders: Stakeholder[];
}) {
  return (
    <div className="relative min-h-[520px] overflow-hidden rounded-md border border-slate-200 bg-white">
      <div className="absolute inset-x-10 top-1/2 border-t border-dashed border-slate-300" />
      <div className="absolute inset-y-10 left-1/2 border-l border-dashed border-slate-300" />
      <span className="absolute left-8 top-8 text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
        Keep satisfied
      </span>
      <span className="absolute right-8 top-8 text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
        Keep close
      </span>
      <span className="absolute bottom-8 left-8 text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
        Monitor
      </span>
      <span className="absolute bottom-8 right-8 text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
        Keep informed
      </span>
      <span className="absolute bottom-4 left-1/2 -translate-x-1/2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
        Importance -&gt;
      </span>
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500 [writing-mode:vertical-rl]">
        Influence -&gt;
      </span>

      {stakeholders.map((stakeholder) => {
        const position = stakeholderPosition(stakeholder);
        const isPriority =
          stakeholder.importance === "high" || stakeholder.influence === "high";
        return (
          <button
            className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-4 py-2 text-sm font-bold shadow-sm outline-none transition hover:-translate-y-[55%] focus-visible:ring-2 focus-visible:ring-[#6f50b5] ${
              isPriority
                ? "border-[#6f50b5] bg-[#eee6fb] text-[#6f50b5]"
                : "border-slate-200 bg-white text-[#292735]"
            }`}
            key={stakeholder.id}
            onClick={() => onEdit(stakeholder)}
            style={{ left: `${position.x}%`, top: `${position.y}%` }}
            type="button"
          >
            <span className="mr-2 text-slate-400">●</span>
            {stakeholder.name}
          </button>
        );
      })}
    </div>
  );
}

function stakeholderPosition(stakeholder: Stakeholder) {
  return {
    x: levelToPercent(stakeholder.importance),
    y: 100 - levelToPercent(stakeholder.influence)
  };
}

function levelToPercent(level: "low" | "medium" | "high") {
  if (level === "high") {
    return 76;
  }
  if (level === "medium") {
    return 50;
  }
  return 24;
}

function stakeholderFromForm(form: FormState, editingId: string | null): Stakeholder {
  return {
    id: editingId ?? crypto.randomUUID(),
    name: form.name.trim(),
    groupType: form.groupType,
    internalOrExternal: form.internalOrExternal,
    relationship: form.relationship.trim() || null,
    importance: form.importance,
    influence: form.influence,
    needs: splitList(form.needs),
    expectations: splitList(form.expectations),
    notes: form.notes.trim() || null,
    evidenceSource: form.evidenceSource.trim(),
    insight: null,
    evidence_ids: []
  };
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function TextField({
  label,
  onChange,
  required = false,
  value
}: {
  label: string;
  onChange: (value: string) => void;
  required?: boolean;
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-purpos-ink">
      {label}
      <input
        className="min-h-10 rounded-lg border border-slate-300 px-3 text-sm outline-none transition focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
        onChange={(event) => onChange(event.target.value)}
        required={required}
        value={value}
      />
    </label>
  );
}

function TextArea({
  label,
  onChange,
  value
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-purpos-ink">
      {label}
      <textarea
        className="min-h-20 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function SelectField({
  label,
  onChange,
  options,
  value
}: {
  label: string;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}) {
  return (
    <label className="grid gap-1 text-sm font-medium text-purpos-ink">
      {label}
      <select
        className="min-h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-purpos-violet focus:ring-2 focus:ring-purpos-violet/20"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
