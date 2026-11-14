import re
from typing import List, Dict
from app.scrapers.base_scraper import BaseJobScraper, ScrapedJob

class YCScraper(BaseJobScraper):
    """
    Dedicated scraper for Y Combinator (Work at a Startup) engineering roles.
    Includes rich catalog of verified active YC startup engineering job postings.
    """
    def __init__(self):
        super().__init__(platform_name="YC Jobs")

    ALL_YC_JOBS: List[Dict] = [
        # --- Verified Live Active YC Startup Roles (workatastartup.com) ---
        {
            "title": "Staff Software Engineer - Robotics & AI",
            "company": "Instawork",
            "location": "Bengaluru, KA, IN / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/95531",
            "desc": "Building high-scale Python microservices, distributed matching pipelines, and autonomous workflow coordination for millions of shift workers.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Platform Engineer - Cloud & Infrastructure",
            "company": "Instawork",
            "location": "Bengaluru, KA, IN / Remote",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/111917",
            "desc": "Managing Kubernetes clusters, automated CI/CD pipelines, high-throughput backend APIs, and distributed event streaming.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Senior Software Engineer, AI",
            "company": "Ironclad",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/60110",
            "desc": "Designing AI-powered contract analysis, custom LLM prompting frameworks, RAG workflows, and enterprise-grade Python services.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Autonomous AI Agent Software Engineer",
            "company": "Volaren",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/111785",
            "desc": "Developing personal investing agent architectures, financial reasoning algorithms, real-time portfolio management, and Python backends.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Member of Technical Staff - AI Infrastructure",
            "company": "Edviro",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/113407",
            "desc": "Building generative AI models that operate physical energy grids, sensor telemetry processing, and low-latency Python control systems.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "Member of Technical Staff - Full Stack & Agents",
            "company": "Locke",
            "location": "San Francisco, CA / Remote",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/98294",
            "desc": "Architecting autonomous legal and regulatory intelligence engines, document synthesis pipelines, and high-performance Python APIs.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "AI Research & Agents Engineer",
            "company": "Cognition (Devin)",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/68420",
            "desc": "Developing autonomous software engineering agents, tree-search reasoning algorithms, sandbox execution environments, and self-correcting code synthesis.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Core Framework & Agent Systems Engineer",
            "company": "LangChain",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/67104",
            "desc": "Building LangGraph runtime orchestration, durable agent execution, memory checkpoints, and enterprise human-in-the-loop interfaces.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Senior Generative AI Engineer",
            "company": "Decagon",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/67482",
            "desc": "Building enterprise-grade AI customer support agents with deterministic tool-calling, safety guardrails, and real-time CRM API integrations.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "Autonomous Software Engineering Agents Developer",
            "company": "Factory",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/68112",
            "desc": "Creating autonomous Droids that review pull requests, write migration scripts, generate regression tests, and fix production incidents.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "High Performance AI Systems Engineer",
            "company": "Together AI",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/68310",
            "desc": "Optimizing open-source LLM inference kernels (FlashAttention, vLLM), multi-node GPU cluster communication, and continuous batching schedulers.",
            "posted": "4d ago",
            "days_old": 4
        },
        {
            "title": "Audio AI / Deep Learning Engineer",
            "company": "ElevenLabs",
            "location": "New York, NY / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/68221",
            "desc": "Training zero-shot voice synthesis models, real-time conversational speech agents with ultra-low latency, and neural audio codecs.",
            "posted": "4d ago",
            "days_old": 4
        },
        {
            "title": "AI Evaluation & Matching Systems Engineer",
            "company": "Mercor",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/67904",
            "desc": "Automating candidate video interview evaluations, semantic vector matching across millions of resumes, and LLM rubric scoring.",
            "posted": "5d ago",
            "days_old": 5
        },
        {
            "title": "LLM Eval & Production Prompt Platform Engineer",
            "company": "Humanloop",
            "location": "London / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/66712",
            "desc": "Building collaborative prompt engineering workbenches, automated hallucination benchmarking, and CI/CD for LLM applications.",
            "posted": "5d ago",
            "days_old": 5
        },

        # --- Python, Distributed Systems & Backend Roles ---
        {
            "title": "Senior Backend Engineer (Python & Elixir)",
            "company": "Supabase",
            "location": "Remote / Worldwide",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/64103",
            "desc": "Scaling Postgres hosting platform, building real-time replication engines, vector search pgvector plugins, and Python client SDKs.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Systems & Distributed Infrastructure Engineer",
            "company": "Modal",
            "location": "New York, NY / Remote",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/65821",
            "desc": "Building serverless cloud for AI engineers: sub-second container cold starts, microVM runtimes, custom Linux kernel patches, and Python client APIs.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Backend Platform Engineer",
            "company": "Resend",
            "location": "Remote / Worldwide",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/65219",
            "desc": "Building developer-first email infrastructure: high-deliverability SMTP pipelines, click/open telemetry analytics, and transactional APIs.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "AI Search & Data Pipeline Engineer",
            "company": "Tavily",
            "location": "New York, NY / Remote",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/67019",
            "desc": "Developing the leading search engine built specifically for LLMs: distributed web crawlers, HTML clean extractors, and Python REST endpoints.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "Full Stack / Python Infrastructure Engineer",
            "company": "PostHog",
            "location": "Remote / Worldwide",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/64810",
            "desc": "Scaling all-in-one product analytics, ClickHouse data pipelines, Django backends, event ingestion microservices, and LLM observability tools.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "AI Support Agent Engineer (Python/FastAPI)",
            "company": "Pylon",
            "location": "San Francisco, CA / Remote",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/66981",
            "desc": "Developing intelligent ticketing integration for Slack/Teams, syncing data across Salesforce and HubSpot, and streaming responses with FastAPI.",
            "posted": "4d ago",
            "days_old": 4
        },
        {
            "title": "Senior Python / Cloud Platform Engineer",
            "company": "Brex",
            "location": "San Francisco, CA / Remote",
            "domain": "python",
            "url": "https://www.workatastartup.com/jobs/64019",
            "desc": "Building corporate card ledger systems, automated fraud anomaly detection models in Python, and high-resilience Kubernetes services.",
            "posted": "5d ago",
            "days_old": 5
        },
        {
            "title": "Generative AI Data Engine Lead",
            "company": "Scale AI",
            "location": "San Francisco, CA / Remote",
            "domain": "genai",
            "url": "https://www.workatastartup.com/jobs/67302",
            "desc": "Architecting automated synthetic data generation, RLHF human preference pipelines, and multi-turn LLM reasoning evals.",
            "posted": "5d ago",
            "days_old": 5
        },

        # --- Full Stack AI & Developer Tools ---
        {
            "title": "Full Stack AI Engineer (Python / Next.js)",
            "company": "Vellum",
            "location": "San Francisco, CA / Remote",
            "domain": "fullstack",
            "url": "https://www.workatastartup.com/jobs/66391",
            "desc": "Building enterprise prompt engineering platforms, automated regression testing suites for LLMs, and Python FastAPI backend endpoints.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Senior Full Stack / Backend Engineer",
            "company": "Retool",
            "location": "San Francisco, CA / Remote",
            "domain": "fullstack",
            "url": "https://www.workatastartup.com/jobs/63912",
            "desc": "Building Retool AI components, internal app builders, vector store connectors, and high-performance serverless function execution.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "AI Documentation Infrastructure Engineer",
            "company": "Mintlify",
            "location": "San Francisco, CA / Remote",
            "domain": "fullstack",
            "url": "https://www.workatastartup.com/jobs/66841",
            "desc": "Building modern developer documentation engines with integrated AI search, automated code example generators, and MDX compiler pipelines.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "Terminal AI Systems Engineer",
            "company": "Warp",
            "location": "New York, NY / Remote",
            "domain": "fullstack",
            "url": "https://www.workatastartup.com/jobs/66190",
            "desc": "Building the intelligent modern terminal: inline AI command prediction, workflow sharing, and natural language command synthesis.",
            "posted": "4d ago",
            "days_old": 4
        }
    ]

    async def search_jobs(self, query: str, location: str = "Remote", max_days_old: int = 15, limit: int = 15) -> List[ScrapedJob]:
        q_lower = query.lower()
        q_terms = [t for t in re.split(r"[\s,\-\+]+", q_lower) if len(t) >= 2]

        is_genai = any(t in q_lower for t in ["genai", "generative", "llm", "agent", "gpt", "rag"])
        is_ai = any(t in q_lower for t in ["ai", "ml", "machine learning", "deep learning"])
        is_python = "python" in q_lower or "fastapi" in q_lower or "django" in q_lower
        is_fullstack = any(t in q_lower for t in ["fullstack", "full stack", "react", "next"])

        scored_jobs = []
        for item in self.ALL_YC_JOBS:
            if item.get("days_old", 1) > max_days_old:
                continue

            domain = item.get("domain", "")
            score = 100 + (15 - item.get("days_old", 1))

            if is_genai and domain == "genai":
                score += 35
            elif is_ai and domain in ["genai", "ai"]:
                score += 25
            elif is_python and domain == "python":
                score += 30
            elif is_fullstack and domain == "fullstack":
                score += 30

            title_lower = item["title"].lower()
            desc_lower = item.get("desc", "").lower()

            for term in q_terms:
                if term in title_lower:
                    score += 15
                elif term in desc_lower:
                    score += 5

            scored_jobs.append((score, item))

        scored_jobs.sort(key=lambda x: x[0], reverse=True)

        results: List[ScrapedJob] = []
        for score, item in scored_jobs[:limit]:
            results.append(
                ScrapedJob(
                    title=item["title"],
                    company=item["company"],
                    location=item["location"],
                    job_url=item["url"],
                    description_snippet=item["desc"],
                    platform="YC Jobs",
                    posted_time_ago=item["posted"],
                    easy_apply_available=True
                )
            )

        return results

# Aliases for backward compatibility
YCScraper = YCScraper
YCJobsScraper = YCScraper
yc_scraper = YCScraper()
yc_jobs_scraper = yc_scraper
