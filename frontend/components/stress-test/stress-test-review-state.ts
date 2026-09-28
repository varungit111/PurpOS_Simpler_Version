export type AgreementLock = { current: string | null };

export function beginAgreement(lock: AgreementLock, criterionId: string) {
  if (lock.current !== null) return false;
  lock.current = criterionId;
  return true;
}

export function endAgreement(lock: AgreementLock, criterionId: string) {
  if (lock.current === criterionId) lock.current = null;
}

export function agreementActionsDisabled(activeCriterionId: string | null) {
  return activeCriterionId !== null;
}

export function setAgreementError(
  errors: Record<string, string>,
  criterionId: string,
  message: string
) {
  return { ...errors, [criterionId]: message };
}

export function clearAgreementError(
  errors: Record<string, string>,
  criterionId: string
) {
  if (!(criterionId in errors)) return errors;
  const next = { ...errors };
  delete next[criterionId];
  return next;
}

export function replaceCriterion<T extends { criterionId: string }>(
  criteria: T[],
  saved: T
) {
  return criteria.map((criterion) =>
    criterion.criterionId === saved.criterionId ? saved : criterion
  );
}
