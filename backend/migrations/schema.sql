-- Database migration for CareerPilot AI: All tables and RLS policies
-- Run this script in the Supabase SQL Editor manually.

-- 1. profiles table
create table if not exists public.profiles (
  id uuid references auth.users(id) on delete cascade primary key,
  full_name text not null,
  email text not null,
  created_at timestamptz default now()
);
alter table public.profiles enable row level security;

-- 2. resumes table
create table if not exists public.resumes (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  filename text not null,
  file_type text not null,
  file_url text, -- Storage public url
  pages integer default 0,
  extracted_text text,
  status text default 'uploaded',
  uploaded_at timestamptz default now()
);
alter table public.resumes enable row level security;

-- 3. resume_analyses table
create table if not exists public.resume_analyses (
  id uuid default gen_random_uuid() primary key,
  resume_id uuid references public.resumes(id) on delete cascade not null,
  user_id uuid references auth.users(id) on delete cascade not null,
  status text not null,
  analysis_results jsonb not null,
  created_at timestamptz default now()
);
alter table public.resume_analyses enable row level security;

-- 4. ats_scores table
create table if not exists public.ats_scores (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  resume_id uuid references public.resumes(id) on delete cascade not null,
  overall_score integer not null,
  keyword_score integer not null,
  format_score integer not null,
  grammar_score integer not null,
  experience_score integer not null,
  recommendations jsonb not null,
  created_at timestamptz default now()
);
alter table public.ats_scores enable row level security;

-- 5. job_matches table
create table if not exists public.job_matches (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  resume_id uuid references public.resumes(id) on delete cascade not null,
  job_description text not null,
  match_percentage integer not null,
  missing_skills jsonb not null,
  matching_skills jsonb not null,
  recommendations jsonb not null,
  created_at timestamptz default now()
);
alter table public.job_matches enable row level security;

-- 6. interview_questions table
create table if not exists public.interview_questions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  resume_id uuid references public.resumes(id) on delete cascade not null,
  questions jsonb not null,
  difficulty text not null,
  category text not null,
  created_at timestamptz default now()
);
alter table public.interview_questions enable row level security;

-- 7. career_roadmaps table
create table if not exists public.career_roadmaps (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  goal text not null,
  current_level text not null,
  roadmap_json jsonb not null,
  created_at timestamptz default now()
);
alter table public.career_roadmaps enable row level security;

-- 8. chat_history table
create table if not exists public.chat_history (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users(id) on delete cascade not null,
  message text not null,
  sender text not null, -- 'user' or 'bot'
  created_at timestamptz default now()
);
alter table public.chat_history enable row level security;

-- Drop existing policies if they exist (to allow safe re-runs)
drop policy if exists "Users can select own profile" on public.profiles;
drop policy if exists "Users can update own profile" on public.profiles;
drop policy if exists "Users can view own resumes" on public.resumes;
drop policy if exists "Users can view their own resumes" on public.resumes;
drop policy if exists "Users can manage own resumes" on public.resumes;
drop policy if exists "Users can view own analyses" on public.resume_analyses;
drop policy if exists "Users can view their own resume analyses" on public.resume_analyses;
drop policy if exists "Users can insert own analyses" on public.resume_analyses;
drop policy if exists "Users can manage own ats_scores" on public.ats_scores;
drop policy if exists "Users can manage own job_matches" on public.job_matches;
drop policy if exists "Users can manage own interview_questions" on public.interview_questions;
drop policy if exists "Users can manage own career_roadmaps" on public.career_roadmaps;
drop policy if exists "Users can manage own chat_history" on public.chat_history;

-- Create strict policies for RLS
create policy "Users can select own profile" on public.profiles for select using (auth.uid() = id);
create policy "Users can update own profile" on public.profiles for update using (auth.uid() = id);
create policy "Users can manage own resumes" on public.resumes for all using (auth.uid() = user_id);
create policy "Users can view own analyses" on public.resume_analyses for select using (auth.uid() = user_id);
create policy "Users can insert own analyses" on public.resume_analyses for insert with check (auth.uid() = user_id);
create policy "Users can manage own ats_scores" on public.ats_scores for all using (auth.uid() = user_id);
create policy "Users can manage own job_matches" on public.job_matches for all using (auth.uid() = user_id);
create policy "Users can manage own interview_questions" on public.interview_questions for all using (auth.uid() = user_id);
create policy "Users can manage own career_roadmaps" on public.career_roadmaps for all using (auth.uid() = user_id);
create policy "Users can manage own chat_history" on public.chat_history for all using (auth.uid() = user_id);

-- =========================================================================
-- 9. Automatic Profile Sync Trigger on successful Auth User Registration
-- =========================================================================

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name, email)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    new.email
  );
  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- =========================================================================
-- 10. Transactional Resume Analysis & Status Update Function (Atomic)
-- =========================================================================

create or replace function public.save_resume_analysis(
  p_resume_id uuid,
  p_user_id uuid,
  p_status text,
  p_analysis_results jsonb
)
returns uuid
language plpgsql
security definer
as $$
declare
  v_analysis_id uuid;
begin
  -- Generate analysis UUID
  v_analysis_id := gen_random_uuid();
  
  -- Insert into public.resume_analyses
  insert into public.resume_analyses (id, resume_id, user_id, status, analysis_results)
  values (v_analysis_id, p_resume_id, p_user_id, p_status, p_analysis_results);
  
  -- Update parent resume status to 'analyzed'
  update public.resumes
  set status = 'analyzed'
  where id = p_resume_id and user_id = p_user_id;
  
  return v_analysis_id;
end;
$$;
