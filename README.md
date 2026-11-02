# AutoApply: Autonomous AI Job Application Agent 🚀

AutoApply is a multi-platform autonomous AI agent that scouts, matches, and applies to high-growth tech openings on **Wellfound (AngelList Startups)** and **Naukri.com** with verified submission proofs, domain role-matching, and a Human-In-The-Loop (HITL) Recruiter Q&A Memory Vault.

Built for **100% Free Production Deployment** with Supabase Multi-Tenant Auth, PostgreSQL Row-Level Security, and Dockerized Headless Playwright Chromium.

---

## 🌟 Key Features

1. **Multi-Platform Autonomous Apply (Playwright Stealth Engine):**
   - **Wellfound Startups:** Automated profile-matching, tailored pitch generation, screening questionnaire handling, and submission.
   - **Naukri.com:** Automated recruiter chatbot interaction, experience extraction, radio/dropdown answers, and 1-click submission.
   - **Y Combinator (Work at a Startup):** Fast portal scout integration.

2. **100% Free Cloud Production Architecture:**
   - **Supabase Auth & PostgreSQL:** Multi-tenant user accounts with Google OAuth, Email/Password, and Row Level Security (RLS).
   - **Hugging Face Docker Space (16 GB RAM Free):** Runs Playwright Headless Chromium reliably without memory limits or crashes.
   - **Vercel / Cloudflare Pages:** Instant global CDN edge frontend with automated GitHub CI/CD.

3. **Recruiter Q&A Memory Vault (Zero Hallucination):**
   - Stores candidate answers to recruiter questions (CTC, notice period, tech stack, experience).
   - If an unknown question arises, the agent alerts the user via **Telegram Bot**, waits for the reply, remembers it forever in the vault, and completes the application.

4. **Visual Proof & Audit Trail:**
   - Automatically captures timestamped high-resolution screenshot proofs upon submission confirmation (e.g., `SUCCESS! YOUR APPLICATION HAS BEEN SENT.` or `✓ Applied`).
   - Clickable `📸 Proof` links provided directly in the frontend table.

5. **AI Resume DNA Extraction:**
   - Parses DOCX, PDF, and TXT resumes to extract technical skills, contact details, experience level, and generate tailored application pitches.

---

## 🛠 Tech Stack

- **Backend:** FastAPI, Python 3.11, Uvicorn, Playwright Chromium, Pydantic, Supabase Python SDK
- **Database & Auth:** Supabase (PostgreSQL 500MB Free Tier, 50,000 MAUs, Row Level Security)
- **Frontend:** HTML5, Modern Tailwind CSS, Lucide Icons, Supabase JS v2, Interactive Scenario Canvas
- **Notifications & HITL:** Telegram Bot API (Async webhook / polling)
- **LLM Reasoning:** Google Gemini API (Free 15 RPM / 1M TPM), Groq, Cohere, Mistral

---

## 🚀 Quick Local Start

```bash
# 1. Clone repository
git clone https://github.com/Sachin-dev001/ai-job-agent.git
cd ai-job-agent

# 2. Setup virtual environment
cd backend
python -m venv venv
venv\Scripts\activate  # Windows (or source venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
playwright install chromium

# 3. Configure environment
copy .env.example .env

# 4. Start backend server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser.

---

## 🌐 100% Free Cloud Deployment

Follow the complete step-by-step instructions in **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**:

1. **Database:** Run `supabase/schema.sql` on **[supabase.com](https://supabase.com)** (Free).
2. **Backend:** Deploy `Dockerfile` to **[Hugging Face Spaces](https://huggingface.co/spaces)** (Free 16 GB RAM Docker).
3. **Frontend:** Connect GitHub repo to **[Vercel](https://vercel.com)** (Free Global CDN).

---

## 🔒 Security & Privacy

- Portal passwords are never stored on any server.
- Database access is strictly governed by PostgreSQL Row-Level Security (`auth.uid() = user_id`).
- All API endpoints support Supabase cryptographic JWT verification.
