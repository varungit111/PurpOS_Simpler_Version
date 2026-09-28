-- PurpOS durable assessment records.
-- Lifecycle metadata remains queryable while the validated assessment model is
-- stored as JSONB so future stages can be added without premature normalization.

create table if not exists public.assessments (
    id uuid primary key,
    lifecycle_status text not null
        check (lifecycle_status in ('created', 'active', 'stage_completed')),
    current_stage text not null
        check (
            current_stage in (
                'identify',
                'define',
                'stress_test',
                'align',
                'results',
                'measure'
            )
        ),
    stage_statuses jsonb not null default '{}'::jsonb,
    assessment_data jsonb not null,
    version integer not null check (version >= 1),
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create index if not exists assessments_updated_at_idx
    on public.assessments (updated_at desc);

alter table public.assessments enable row level security;

-- No browser-facing RLS policy is created. The backend uses its service-role key,
-- which bypasses RLS, and assessment persistence stays behind the FastAPI API.
