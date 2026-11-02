---
title: Autoapply Api
emoji: ⚡
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
---

# AutoApply: Autonomous AI Job Application Agent 🚀

AutoApply is a multi-platform autonomous AI agent that scouts, matches, and applies to high-growth tech openings on **Wellfound (AngelList Startups)** and **Naukri.com** with verified submission proofs, domain role-matching, and a Human-In-The-Loop (HITL) Recruiter Q&A Memory Vault.

Built for **100% Free Production Deployment** with Supabase Multi-Tenant Auth, PostgreSQL Row-Level Security, and Headless Playwright Chromium.

---

## 🌟 Key Features

1. **Multi-Platform Autonomous Apply (Playwright Stealth Engine):**
   - **Wellfound Startups:** Automated profile-matching, tailored pitch generation, screening questionnaire handling, and submission.
   - **Naukri.com:** Automated recruiter chatbot interaction, experience extraction, radio/dropdown answers, and 1-click submission.
   - **Y Combinator (Work at a Startup):** Fast portal scout integration.

2. **100% Free Cloud Production Architecture:**
   - **Supabase Auth & PostgreSQL:** Multi-tenant user accounts with Google OAuth, Email/Password, and Row Level Security (RLS).
   - **Hugging Face Cloud Engine:** Runs Playwright Chromium and FastAPI REST endpoints.
   - **Vercel / Cloudflare Pages:** Instant global CDN edge frontend with automated GitHub CI/CD.

3. **Recruiter Q&A Memory Vault (Zero Hallucination):**
   - Stores candidate answers to recruiter questions (CTC, notice period, tech stack, experience).
   - If an unknown question arises, the agent alerts the user via **Telegram Bot**, waits for the reply, remembers it forever in the vault, and completes the application.

4. **Visual Proof & Audit Trail:**
   - Automatically captures timestamped high-resolution screenshot proofs upon submission confirmation.

5. **AI Resume DNA Extraction:**
   - Parses DOCX, PDF, and TXT resumes with Google Gemini Flash to extract technical skills, contact details, experience level, and generate tailored application pitches.
