export const ASSESSMENT_POINTER_KEY = "purpos:lastAssessmentId";

type AssessmentPointerStorage = Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;

function browserStorage(): AssessmentPointerStorage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function getRememberedAssessment(
  storage: AssessmentPointerStorage | null = browserStorage()
): string | null {
  return storage?.getItem(ASSESSMENT_POINTER_KEY) ?? null;
}

export function rememberAssessment(
  assessmentId: string,
  storage: AssessmentPointerStorage | null = browserStorage()
): void {
  storage?.setItem(ASSESSMENT_POINTER_KEY, assessmentId);
}

export function clearRememberedAssessment(
  storage: AssessmentPointerStorage | null = browserStorage()
): void {
  storage?.removeItem(ASSESSMENT_POINTER_KEY);
}

export function isConfirmedUnusableAssessmentStatus(status: number): boolean {
  return status === 404 || status === 422;
}

export async function validateRememberedAssessment<
  Session extends { id: string }
>(options: {
  assessmentId: string;
  loadSession: (assessmentId: string) => Promise<Session | null>;
  resumePath: (session: Session) => string | null;
  storage?: AssessmentPointerStorage | null;
}): Promise<Session | null> {
  const { assessmentId, loadSession, resumePath, storage = browserStorage() } =
    options;

  try {
    const session = await loadSession(assessmentId);
    if (!session) {
      clearRememberedAssessment(storage);
      return null;
    }
    if (!resumePath(session)) {
      return null;
    }

    rememberAssessment(session.id, storage);
    return session;
  } catch {
    return null;
  }
}
