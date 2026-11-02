# 🚀 AutoApply: 100% Free Production Deployment Guide

Deploy **AutoApply** as a multi-user, production-grade cloud SaaS platform using verified **100% free-tier infrastructure ($0.00/month forever)**.

---

## 🏗 System Architecture Overview

```
                      +------------------------------------------+
                      |         End Users (Web Browser)          |
                      +------------------------------------------+
                                    |               |
                      (HTML/Tailwind Assets)   (OAuth / Email)
                                    |               |
                                    v               v
                      +-------------------+   +--------------------+
                      |   Vercel Edge     |   |   Supabase Auth    |
                      |   Global CDN      |   |   (50k Users Free) |
                      +-------------------+   +--------------------+
                                    |               |
                           (API Calls + JWT Token)  |
                                    |               |
                                    v               v
                      +------------------------------------------+
                      |  Hugging Face Docker Space (16 GB RAM)   |
                      |  - FastAPI REST & WebSocket Engine       |
                      |  - Playwright Headless Chromium Engine   |
                      |  - Human-in-the-Loop Telegram Gateway    |
                      +------------------------------------------+
                                    |               |
                         (RLS Data Queries)   (Proof Uploads)
                                    |               |
                                    v               v
                      +-------------------+   +--------------------+
                      | Supabase Postgres |   |  Supabase Storage  |
                      | (500MB Free Tier) |   | (1GB Proof Bucket) |
                      +-------------------+   +--------------------+
```

---

## Step 1: Set Up Free Cloud Database & Auth (Supabase)

1. Go to **[supabase.com](https://supabase.com)** and create a free account (no credit card required).
2. Click **"New project"**, name it `autoapply-cloud`, choose your preferred region, and set a database password.
3. Once the project dashboard is ready, click **SQL Editor** in the left sidebar.
4. Open the SQL script in your repository: [`supabase/schema.sql`](supabase/schema.sql).
5. Copy all lines, paste them into the Supabase SQL Editor, and click **Run**.
   - *This creates all tables (`profiles`, `qa_memory`, `job_applications`, `user_resumes`) and enables Row-Level Security (RLS) so users' data is strictly isolated.*
6. In **Project Settings** -> **API**, copy the following values:
   - **Project URL**
   - **Project API Keys** -> `anon` (public key)
   - **Project API Keys** -> `service_role` (secret key)
   - **JWT Settings** -> `JWT Secret`

---

## Step 2: Deploy Backend to Hugging Face Spaces (16 GB RAM Free Docker)

> **Why Hugging Face Spaces?**  
> Headless Playwright Chromium requires 600MB–1.2GB RAM. Standard free tiers (like Render or Railway) crash due to memory exhaustion. Hugging Face Spaces gives **2 vCPU and 16 GB of RAM for free**, making it the best platform to run Playwright in the cloud.

1. Go to **[huggingface.co/spaces](https://huggingface.co/spaces)** and sign in.
2. Click **"Create new Space"**:
   - **Space name**: `autoapply-api`
   - **Space SDK**: Select **Docker** -> **Blank**
   - **Visibility**: Public (or Private)
3. Under your new Space, click **Settings** -> **Variables and secrets** -> **New secret**:
   - `SUPABASE_URL`: `<your-supabase-project-url>`
   - `SUPABASE_ANON_KEY`: `<your-supabase-anon-key>`
   - `SUPABASE_SERVICE_ROLE_KEY`: `<your-supabase-service-role-key>`
   - `SUPABASE_JWT_SECRET`: `<your-supabase-jwt-secret>`
   - `GEMINI_API_KEY`: `<your-free-gemini-key-from-aistudio.google.com>`
   - `TELEGRAM_BOT_TOKEN`: `<optional-telegram-bot-token>`
   - `TELEGRAM_CHAT_ID`: `<optional-telegram-chat-id>`
   - `REQUIRE_AUTH`: `false` (or `true` if you want strict login required)
4. Push this repository to Hugging Face:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/autoapply-api
   git push space main
   ```
5. Hugging Face will automatically build the `Dockerfile` with Playwright Chromium. Within 2-3 minutes, your API will be live at:
   `https://<your-username>-autoapply-api.hf.space`

---

## Step 3: Deploy Frontend to Vercel or Cloudflare Pages (Free Global CDN)

1. Go to **[vercel.com](https://vercel.com)** and sign in with GitHub.
2. Click **"Add New Project"** and import your repository: `Sachin-dev001/ai-job-agent`.
3. In Project Settings:
   - **Root Directory**: Select `frontend`
   - **Framework Preset**: Other (Static HTML)
4. Click **Deploy**.
5. Within 20 seconds, your AutoApply interface is live worldwide with free SSL!

---

## Step 4: Connect Google OAuth (Optional & 100% Free)

To allow users to sign in with **1-click Google**:
1. Open your **[Google Cloud Console](https://console.cloud.google.com)**.
2. Create an **OAuth 2.0 Client ID** (Web Application).
3. Set the Authorized Redirect URI to your Supabase Auth callback URL:
   `https://<your-project-id>.supabase.co/auth/v1/callback`
4. Copy the **Client ID** and **Client Secret** into your Supabase Dashboard under **Authentication** -> **Providers** -> **Google**.
5. Click Save. Users can now sign in with Google instantly!

---

## 🔒 Security Best Practices Implemented

- **PostgreSQL Row Level Security (RLS)**: User A cannot read or modify User B's resumes, applications, or screening memory answers.
- **Zero Server Credentials**: Third-party portal passwords are never saved on the server.
- **JWT Cryptographic Verification**: Every API call verifies token claims before running agent tasks.
- **Local Fallback Mode**: Even without cloud credentials configured, the agent runs seamlessly in offline local mode for testing.
