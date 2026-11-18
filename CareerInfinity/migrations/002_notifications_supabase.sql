-- Supabase-ready schema artifact for a future Supabase-auth deployment.
-- The current application authenticates with Firebase and stores data in SQLite;
-- this migration is not used by the current runtime.

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (length(title) between 1 and 200),
  message text not null check (length(message) between 1 and 4000),
  category text not null check (category in ('job_match','internship','application','interview','deadline','ai_insight')),
  notification_type text,
  job_id uuid,
  company_name text,
  match_percentage integer check (match_percentage is null or match_percentage between 0 and 100),
  is_read boolean not null default false,
  action_url text,
  created_at timestamptz not null default now(),
  dedupe_key text,
  is_demo boolean not null default false,
  unique (user_id, dedupe_key)
);

create index if not exists idx_notifications_user_created
  on public.notifications (user_id, created_at desc, id);
create index if not exists idx_notifications_user_read_created
  on public.notifications (user_id, is_read, created_at desc);
create index if not exists idx_notifications_user_category_created
  on public.notifications (user_id, category, created_at desc);

alter table public.notifications enable row level security;
revoke all on public.notifications from anon;
grant select, delete on public.notifications to authenticated;
revoke update on public.notifications from authenticated;
grant update (is_read) on public.notifications to authenticated;

drop policy if exists "Users can read their notifications" on public.notifications;
create policy "Users can read their notifications"
  on public.notifications for select to authenticated
  using (user_id = (select auth.uid()));

drop policy if exists "Users can update their notification read status" on public.notifications;
create policy "Users can update their notification read status"
  on public.notifications for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

drop policy if exists "Users can delete their notifications" on public.notifications;
create policy "Users can delete their notifications"
  on public.notifications for delete to authenticated
  using (user_id = (select auth.uid()));

-- No INSERT policy is granted to authenticated users. Trusted server-side jobs
-- may insert with the service role; that secret must never reach the browser.

create table if not exists public.notification_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preferences jsonb not null default '{
    "job_matches": true,
    "internships": true,
    "application_updates": true,
    "interview_reminders": true,
    "deadline_reminders": true,
    "ai_insights": true,
    "email_notifications": false,
    "in_app_notifications": true,
    "preferred_roles": [],
    "preferred_locations": [],
    "work_modes": ["Remote", "Hybrid", "On-site"],
    "job_types": ["Internship", "Full-time"],
    "minimum_match_percentage": 70
  }'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.notification_preferences enable row level security;
revoke all on public.notification_preferences from anon;
grant select, insert, update on public.notification_preferences to authenticated;
drop policy if exists "Users manage their own notification preferences" on public.notification_preferences;
create policy "Users manage their own notification preferences"
  on public.notification_preferences for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

-- Enable Realtime publication for inserts and preference-independent updates.
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'notifications'
  ) then
    alter publication supabase_realtime add table public.notifications;
  end if;
end $$;
