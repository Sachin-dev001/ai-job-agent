-- ==============================================================================
-- AutoApply Cloud Database Schema & Multi-Tenant Row Level Security (RLS)
-- Target Platform: Supabase PostgreSQL (100% Free Tier)
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. USER PROFILES TABLE (Linked directly to Supabase Auth)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    phone TEXT,
    location TEXT DEFAULT 'Bengaluru, India',
    current_ctc TEXT DEFAULT '7 LPA',
    expected_ctc TEXT DEFAULT '10 LPA',
    notice_period TEXT DEFAULT '15 Days',
    experience_years NUMERIC DEFAULT 2.0,
    primary_domain TEXT DEFAULT 'AI/Software Engineering',
    linkedin_url TEXT,
    github_url TEXT,
    telegram_chat_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. USER RESUMES TABLE
CREATE TABLE IF NOT EXISTS public.user_resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    file_size INTEGER,
    parsed_skills JSONB DEFAULT '[]'::jsonb,
    parsed_profile JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. RECRUITER Q&A MEMORY VAULT (Candidate Permanent Memory)
CREATE TABLE IF NOT EXISTS public.qa_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT DEFAULT 'custom',
    keywords TEXT[] DEFAULT ARRAY[]::TEXT[],
    learned_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. JOB APPLICATIONS TRACKER
CREATE TABLE IF NOT EXISTS public.job_applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL, -- 'naukri', 'wellfound', 'ycombinator', 'linkedin'
    job_title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    job_url TEXT NOT NULL,
    location TEXT,
    salary_range TEXT,
    match_score NUMERIC DEFAULT 0.0,
    status TEXT DEFAULT 'discovered', -- 'discovered', 'queued', 'in_progress', 'applied', 'skipped', 'failed'
    cover_letter TEXT,
    proof_screenshot_url TEXT,
    error_message TEXT,
    applied_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. PENDING RECRUITER SCREENING QUESTIONS (HITL Gateway)
CREATE TABLE IF NOT EXISTS public.recruiter_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    job_url TEXT,
    question TEXT NOT NULL,
    options JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'pending', -- 'pending', 'answered', 'skipped'
    asked_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    answered_at TIMESTAMP WITH TIME ZONE
);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- Guarantee strict tenant data isolation (User A cannot access User B data)
-- ==============================================================================

-- Enable RLS on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qa_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recruiter_questions ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
CREATE POLICY "Users can view own profile" ON public.profiles
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON public.profiles
    FOR UPDATE USING (auth.uid() = id);

-- User Resumes Policies
CREATE POLICY "Users can manage own resumes" ON public.user_resumes
    FOR ALL USING (auth.uid() = user_id);

-- Q&A Memory Policies
CREATE POLICY "Users can manage own QA memory" ON public.qa_memory
    FOR ALL USING (auth.uid() = user_id);

-- Job Applications Policies
CREATE POLICY "Users can manage own applications" ON public.job_applications
    FOR ALL USING (auth.uid() = user_id);

-- Recruiter Questions Policies
CREATE POLICY "Users can manage own recruiter questions" ON public.recruiter_questions
    FOR ALL USING (auth.uid() = user_id);

-- ==============================================================================
-- AUTOMATIC PROFILE CREATION TRIGGER ON SIGNUP
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
    );

    -- Seed default screening Q&A template for new user
    INSERT INTO public.qa_memory (user_id, question, answer, category, keywords)
    VALUES
        (NEW.id, 'Are you willing to relocate?', 'Yes', 'location', ARRAY['relocate', 'relocation']),
        (NEW.id, 'What is your notice period?', '15 Days', 'availability', ARRAY['notice', 'joining', 'days']),
        (NEW.id, 'What is your highest qualification?', 'B.Tech in Computer Science', 'education', ARRAY['degree', 'qualification', 'education']);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger execution
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==============================================================================
-- STORAGE BUCKETS SETUP (Execute in Supabase Storage or Dashboard)
-- ==============================================================================
-- INSERT INTO storage.buckets (id, name, public) VALUES ('resumes', 'resumes', false);
-- INSERT INTO storage.buckets (id, name, public) VALUES ('proofs', 'proofs', true);
