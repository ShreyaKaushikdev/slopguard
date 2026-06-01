-- =============================================================================
-- SlopGuard Adaptive Baselines & Live Ticker — Supabase Migration
-- =============================================================================
-- Run this in your Supabase project SQL editor or via `supabase migration up`
-- =============================================================================

-- 1. Repo Baselines
create table if not exists repo_baselines (
  repo_id text primary key,  -- "facebook/react"
  domain text not null default 'code_review',
  sample_count integer not null default 0,
  mean_score float not null default 0.0,
  std_dev float not null default 0.0,
  min_score float not null default 100.0,
  max_score float not null default 0.0,
  percentiles jsonb default '{"p25": 0, "p50": 0, "p75": 0, "p90": 0}',
  last_updated timestamp with time zone not null default now()
);

create index if not exists idx_repo_baselines_domain on repo_baselines(domain);

-- 2. Author Baselines
create table if not exists author_baselines (
  author_id text not null,            -- github username
  repo_id text not null,
  domain text not null default 'code_review',
  sample_count integer not null default 0,
  mean_score float not null default 0.0,
  std_dev float not null default 0.0,
  min_score float not null default 100.0,
  max_score float not null default 0.0,
  why_ratio float default 0.0,        -- their personal WHY/WHAT ratio
  specificity_mean float default 0.0,
  last_updated timestamp with time zone not null default now(),
  primary key (author_id, repo_id, domain)
);

-- 3. Global Baselines per domain
create table if not exists global_baselines (
  domain text primary key,
  sample_count integer not null default 0,
  mean_score float not null default 0.0,
  std_dev float not null default 0.0,
  min_score float not null default 100.0,
  max_score float not null default 0.0,
  percentiles jsonb default '{"p25": 0, "p50": 0, "p75": 0, "p90": 0}',
  last_updated timestamp with time zone not null default now()
);

-- 4. Alter existing score_events table to add ticker/baseline fields
alter table if exists score_events
  add column if not exists domain text,
  add column if not exists repo_id text,
  add column if not exists author_id text,
  add column if not exists top_signal text,       -- which signal contributed most
  add column if not exists is_slop boolean;       -- score below global mean

create index if not exists idx_score_events_created_at on score_events(created_at desc);
create index if not exists idx_score_events_domain on score_events(domain);
create index if not exists idx_score_events_repo_id on score_events(repo_id);

-- 5. Enable realtime on score_events for the live ticker
alter publication supabase_realtime add table score_events;

-- 6. Row-level security (optional — enable if using per-user telemetry)
-- alter table repo_baselines enable row level security;
-- alter table author_baselines enable row level security;
-- alter table global_baselines enable row level security;

-- 7. Useful view: recent activity for ticker
create or replace view ticker_recent_60s as
select
  count(*) as total_scored,
  domain,
  avg(score) as avg_score,
  stddev(score) as std_dev_score,
  count(*) filter (where is_slop = true) as slop_count
from score_events
where created_at > now() - interval '60 seconds'
group by domain;

-- 8. Useful view: per-repo summary
create or replace view repo_summary as
select
  repo_id,
  domain,
  count(*) as total_scored,
  avg(score) as avg_score,
  stddev(score) as std_dev_score,
  max(created_at) as last_scored
from score_events
where repo_id is not null
group by repo_id, domain;

-- 9. Useful view: top signals trending
create or replace view trending_signals as
select
  top_signal,
  count(*) as occurrence_count,
  count(*) * 100.0 / sum(count(*)) over () as percentage
from score_events
where created_at > now() - interval '60 seconds'
  and top_signal is not null
group by top_signal
order by occurrence_count desc;
