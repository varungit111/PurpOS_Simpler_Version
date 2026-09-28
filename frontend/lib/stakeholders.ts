import { z } from "zod";
import { API_BASE_URL } from "./api-config";

export const stakeholderSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  groupType: z.enum([
    "customer",
    "employee",
    "supplier",
    "partner",
    "owner",
    "investor",
    "community",
    "regulator",
    "other"
  ]),
  internalOrExternal: z.enum(["internal", "external", "both"]),
  relationship: z.string().min(1).nullable(),
  importance: z.enum(["low", "medium", "high"]),
  influence: z.enum(["low", "medium", "high"]),
  needs: z.array(z.string().min(1)),
  expectations: z.array(z.string().min(1)),
  notes: z.string().min(1).nullable(),
  evidenceSource: z.string().min(1),
  insight: z.string().min(1).nullable(),
  evidence_ids: z.array(z.string().uuid())
});

const stakeholderMapResponseSchema = z.object({
  activity_id: z.literal("who-matters"),
  stakeholders: z.array(stakeholderSchema)
});

export type Stakeholder = z.infer<typeof stakeholderSchema>;

export async function getStakeholders(sessionId: string): Promise<Stakeholder[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/stakeholders`
  );

  if (!response.ok) {
    throw new Error("Unable to load stakeholders.");
  }

  const payload = stakeholderMapResponseSchema.parse(await response.json());
  return payload.stakeholders;
}

export async function saveStakeholders({
  sessionId,
  stakeholders
}: {
  sessionId: string;
  stakeholders: Stakeholder[];
}): Promise<Stakeholder[]> {
  const response = await fetch(
    `${API_BASE_URL}/api/sessions/${sessionId}/identify/stakeholders`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ stakeholders })
    }
  );

  if (!response.ok) {
    throw new Error("Unable to save stakeholders.");
  }

  const payload = stakeholderMapResponseSchema.parse(await response.json());
  return payload.stakeholders;
}
