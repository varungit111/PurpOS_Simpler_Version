# Supabase Assessment Persistence

PurpOS selects one `AssessmentRepository` adapter at backend startup. All
session, Identify, and orchestrator operations continue through `SessionStore`.

## Repository selection

For non-durable local or test use:

```env
PURPOS_ASSESSMENT_REPOSITORY=memory
```

For durable Supabase persistence:

```env
PURPOS_ASSESSMENT_REPOSITORY=supabase
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_BACKEND_ONLY_SERVICE_ROLE_KEY
```

Never expose the service-role key to the frontend or place it in a
`NEXT_PUBLIC_*` variable. The backend fails during startup when Supabase is
selected and either credential is missing; it does not fall back to memory.

For local development, place these values in `backend/.env` and start the API
from `backend/` with:

```bash
uvicorn app.main:app --reload
```

The backend loads `backend/.env` automatically. Existing process environment
variables take precedence, so deployment and one-off shell overrides continue
to work without modifying the local file.

## Apply the migration

Open the Supabase SQL Editor for the target project and run:

`supabase/migrations/20260919_create_assessments.sql`

The migration creates one `public.assessments` table. Important lifecycle
metadata is stored in normal columns, while the complete validated assessment
record is stored in `assessment_data` JSONB. Row-level security is enabled and
no browser-facing policy is added because only the backend service role should
access this table.

## Persisted and temporary data

Persisted data includes the assessment ID, organisation context, current stage,
lifecycle and per-stage status, stage state, structured outputs, handoffs,
revisit routes, complete Identify output/evidence/coverage, provenance,
timestamps, version, and future-stage containers.

Raw conversation turns remain temporary. The orchestrator saves resumable
structured context with the `turns` collection removed, matching the technical
architecture's retention boundary.

## Verify restart persistence

1. Apply the migration.
2. Configure the three Supabase environment variables above.
3. Start the backend and create an assessment through the existing UI.
4. Complete or save an Identify activity and retain the assessment ID.
5. Stop and restart the backend process.
6. Request `GET /api/sessions/{assessment_id}` or reopen the frontend.
7. Confirm the backend returns the same lifecycle, Identify evidence, coverage,
   timestamps, and version, and that the frontend resumes the Identify board.

Normal automated tests use mocked HTTP transport and do not contact Supabase.
