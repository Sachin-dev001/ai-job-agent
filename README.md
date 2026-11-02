# Autonomous AI Job Application Agent 🚀

An autonomous, multi-platform AI agent designed to scout, match, and apply to job openings on **Wellfound (AngelList Startups)** and **Naukri.com** with verified submission proofs, strict domain role-matching, and a Human-In-The-Loop (HITL) Recruiter Q&A Memory Vault.

---

## 🌟 Key Features

1. **Multi-Platform Autonomous Apply (Playwright Stealth Engine):**
   - **Wellfound (AngelList) Startups:** Automated profile-matching, tailored pitch note generation, screening questionnaire handling, and direct founder/recruiter application submission.
   - **Naukri.com Workspace:** Automated chatbot interaction, experience extraction, radio/dropdown answers, and verified 1-click submission.
   - **Y Combinator (Work at a Startup):** Dedicated workspace prepared for upcoming integration.

2. **Strict Domain-Level Role Separation & Freshness Filter:**
   - Filters jobs strictly to postings within **$\le$ 15 days** (sorted newest to oldest).
   - **Domain Isolation:** Prevents role cross-contamination (e.g., searching *Data Analyst* strictly shows Data Analyst roles without leaking Data Engineering or ML roles).

3. **Recruiter Q&A Memory Vault (Zero Hallucination):**
   - Stores candidate answers to recruiter questions (CTC, notice period, tech stack, experience).
   - If an unknown question arises during an application, the agent alerts the user via **Telegram Bot**, waits for the reply, remembers it forever in the vault, and completes the application.

4. **Visual Proof & Audit Trail:**
   - Automatically captures timestamped high-resolution screenshot proofs upon submission confirmation (e.g., `SUCCESS! YOUR APPLICATION HAS BEEN SENT.` or `✓ Applied`).
   - Clickable `📸 Proof` links provided directly in the frontend table.

5. **AI Resume DNA Extraction:**
   - Parses DOCX, PDF, and TXT resumes to extract technical skills, contact details, experience level, and generate tailored application pitches.

---

## 🛠 Tech Stack

- **Backend:** FastAPI, Python 3.11, Uvicorn, Pydantic, Playwright (Chromium with Playwright Stealth)
- **Frontend:** HTML5, Modern Tailwind CSS, Lucide Icons, Vanilla ES6+ JavaScript
- **Memory & HITL:** SQLite / JSON persistence, Telegram Bot API (Async Long Polling)
- **LLM Integrations:** Groq (Qwen / LLaMA), Google Gemini API, Cohere

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Sachin-dev001/ai-job-agent.git
cd ai-job-agent
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your API keys:
```bash
cp backend/.env.example backend/.env
```
Fill in:
- `GROQ_API_KEY` or `GEMINI_API_KEY` (Free Cloud LLMs)
- `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` (For Human-In-The-Loop alerts)

### 3. Setup Virtual Environment
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 4. Run the Agent
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at `http://localhost:8000`.

---

## 📂 Project Structure

```
ai-job-agent/
├── backend/
│   ├── app/
│   │   ├── agents/          # Job scout & Playwright automation runners
│   │   ├── scrapers/        # Platform scrapers (Naukri, Wellfound, RemoteOK)
│   │   ├── memory/          # Recruiter Q&A Memory Vault
│   │   ├── notifications/   # Telegram Bot HITL listener & dispatcher
│   │   └── llm/             # LLM orchestrator (Groq / Gemini)
│   ├── cookies/             # Authenticated platform session cookies (.gitignored)
│   ├── data/                # Persistent QA memories & pending questions
│   ├── proofs/              # High-resolution submission screenshot proofs (.gitignored)
│   ├── main.py              # FastAPI application entrypoint
│   └── requirements.txt
├── frontend/
│   ├── static/
│   │   ├── css/
│   │   └── js/app.js        # Reactive dashboard & auto-apply controller
│   └── index.html           # Modern glassmorphism dashboard UI
├── .gitignore
└── README.md
```

---

## 🔒 Security & Privacy

All session cookies (`backend/cookies/*.json`), environment files (`.env`), browser cache profiles (`backend/browser_profile/`), and uploaded resumes (`backend/uploads/`) are strictly excluded by `.gitignore` to prevent leaking private credentials or tokens.

---

## 📄 License
MIT License. Free for open-source and personal automation workflows.
