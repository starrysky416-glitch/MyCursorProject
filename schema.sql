-- Supabase SQL Editor에서 한 번 실행하세요.
-- Dashboard → SQL Editor → New query → Run

create table if not exists public.classified_work (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  academic_year integer not null,
  title_count integer not null default 0,
  raw_text text,
  payload jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  unique (user_id, academic_year)
);

alter table public.classified_work enable row level security;

drop policy if exists "사용자는 자기 업무만 관리" on public.classified_work;
create policy "사용자는 자기 업무만 관리"
on public.classified_work
for all
to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

grant select, insert, update, delete on table public.classified_work to authenticated;
