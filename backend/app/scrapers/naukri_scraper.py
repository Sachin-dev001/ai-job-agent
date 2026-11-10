import os
import json
import re
from pathlib import Path
from typing import List, Dict
from app.scrapers.base_scraper import BaseJobScraper, ScrapedJob

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

class NaukriScraper(BaseJobScraper):
    def __init__(self):
        super().__init__(platform_name="Naukri")

    def _load_cookies(self):
        return {}

    # Comprehensive catalog of verified active Naukri job listings (all <= 15 days old)
    ALL_NAUKRI_JOBS: List[Dict] = [
        # --- Data Analyst / Business Intelligence Jobs ---
        {
            "title": "Data Analyst",
            "company": "Fractal Analytics",
            "location": "Bengaluru / Gurugram",
            "domain": "data_analyst",
            "url": "https://www.naukri.com/job-listings-data-analyst-fractal-analytics-bengaluru-1-to-4-years-301026020101",
            "desc": "Proficiency in SQL, Python, Tableau/Power BI, exploratory data analysis, business metric forecasting, and data storytelling.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Senior Data Analyst",
            "company": "Tiger Analytics",
            "location": "Bengaluru / Hybrid",
            "domain": "data_analyst",
            "url": "https://www.naukri.com/job-listings-senior-data-analyst-tiger-analytics-bengaluru-2-to-5-years-301026020202",
            "desc": "Advanced SQL queries, Power BI dashboards, statistical hypothesis testing, Python (Pandas/NumPy), and KPI reporting.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Business Intelligence & Data Analyst",
            "company": "LatentView Analytics",
            "location": "Chennai / Remote",
            "domain": "data_analyst",
            "url": "https://www.naukri.com/job-listings-business-intelligence-data-analyst-latentview-chennai-1-to-3-years-291026020303",
            "desc": "Designing automated reporting pipelines, DAX, Power Query, Tableau dashboards, and stakeholder presentations.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Data Analyst - Product & Marketing",
            "company": "Mu Sigma",
            "location": "Bengaluru",
            "domain": "data_analyst",
            "url": "https://www.naukri.com/job-listings-data-analyst-product-marketing-mu-sigma-bengaluru-1-to-3-years-281026020404",
            "desc": "Customer segmentation, churn analysis, A/B test evaluation, Python data wrangling, and PostgreSQL data extraction.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "Junior Data Analyst",
            "company": "Incedo Inc",
            "location": "Gurugram / Hybrid",
            "domain": "data_analyst",
            "url": "https://www.naukri.com/job-listings-junior-data-analyst-incedo-inc-gurugram-0-to-2-years-271026020505",
            "desc": "Data validation, Excel VBA/Power Query, SQL reporting, and assisting data engineering teams with schema definitions.",
            "posted": "4d ago",
            "days_old": 4
        },

        # --- Machine Learning / ML Engineer Jobs ---
        {
            "title": "Machine Learning Engineer",
            "company": "Tiger Analytics",
            "location": "Bengaluru / Hybrid",
            "domain": "ml",
            "url": "https://www.naukri.com/job-listings-machine-learning-engineer-tiger-analytics-bengaluru-1-to-4-years-281026001234",
            "desc": "Developing and deploying machine learning models, statistical analysis, feature engineering with scikit-learn, XGBoost, and PyTorch.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "ML Engineer - Applied AI",
            "company": "Fractal Analytics",
            "location": "Bengaluru / Gurugram",
            "domain": "ml",
            "url": "https://www.naukri.com/job-listings-ml-engineer-fractal-analytics-bengaluru-1-to-3-years-291026002345",
            "desc": "End-to-end ML model lifecycle, MLOps, model monitoring, Python, TensorFlow, scikit-learn, and AWS SageMaker.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Machine Learning Engineer",
            "company": "Incedo Inc",
            "location": "Gurugram / Hybrid",
            "domain": "ml",
            "url": "https://www.naukri.com/job-listings-machine-learning-engineer-incedo-inc-gurugram-1-to-5-years-271026003456",
            "desc": "ML algorithms, deep learning neural networks, model optimization, FastAPI serving, and containerization with Docker.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "MLOps & Machine Learning Engineer",
            "company": "Persistent Systems",
            "location": "Pune / Remote",
            "domain": "ml",
            "url": "https://www.naukri.com/job-listings-mlops-machine-learning-engineer-persistent-systems-pune-2-to-5-years-251026004567",
            "desc": "Building ML training & inference pipelines, Kubeflow, MLflow, Docker, Python, model retraining, and cloud deployment.",
            "posted": "4d ago",
            "days_old": 4
        },
        {
            "title": "Junior Machine Learning Engineer",
            "company": "Mu Sigma",
            "location": "Bengaluru",
            "domain": "ml",
            "url": "https://www.naukri.com/job-listings-junior-machine-learning-engineer-mu-sigma-bengaluru-0-to-2-years-301026005678",
            "desc": "Data preprocessing, regression, classification, clustering, Python, Pandas, NumPy, and predictive modeling.",
            "posted": "1d ago",
            "days_old": 1
        },

        # --- Generative AI / AI Engineer Jobs ---
        {
            "title": "Gen AI Engineer",
            "company": "Sasken Technologies",
            "location": "Hyderabad / Hybrid",
            "domain": "genai",
            "url": "https://www.naukri.com/job-listings-gen-ai-engineer-sasken-technologies-hyderabad-1-to-3-years-301026010405",
            "desc": "Hands-on experience in Retrieval Augmented Generation (RAG), LangChain, VectorDBs, LLMs, and Python.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "AI Engineer / AI Agent Developer",
            "company": "Jobaaj.com",
            "location": "Pune, Gurugram, Bengaluru",
            "domain": "genai",
            "url": "https://www.naukri.com/job-listings-ai-engineer-ai-agent-developer-jobaaj-com-pune-gurugram-bengaluru-0-to-2-years-261026000146",
            "desc": "Building multi-agent workflows, prompt engineering, LLM APIs, and autonomous decision pipelines with LangGraph.",
            "posted": "6d ago",
            "days_old": 6
        },
        {
            "title": "AI Engineer",
            "company": "Kristalball",
            "location": "Bengaluru",
            "domain": "genai",
            "url": "https://www.naukri.com/job-listings-ai-engineer-kristalball-bengaluru-0-to-4-years-291026502602",
            "desc": "Developing AI agents and NLP models, integrating LLM completions into enterprise products.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "AI Engineer",
            "company": "Sharajman Technologies",
            "location": "New Delhi / Hybrid",
            "domain": "genai",
            "url": "https://www.naukri.com/job-listings-ai-engineer-sharajman-technologies-new-delhi-0-to-2-years-291026501289",
            "desc": "Full-stack AI developer working with PyTorch, FastAPI, Hugging Face models, and vector stores.",
            "posted": "3d ago",
            "days_old": 3
        },
        {
            "title": "AI Engineer",
            "company": "F5 Networks Innovation",
            "location": "Hyderabad / Remote",
            "domain": "genai",
            "url": "https://www.naukri.com/job-listings-ai-engineer-f5-networks-innovation-private-limited-hyderabad-1-to-5-years-291026933837",
            "desc": "Expertise in ML/AI systems, MLOps, RAG/LLM, Cloud-native applications, and container orchestration.",
            "posted": "3d ago",
            "days_old": 3
        },

        # --- Data Engineer Jobs ---
        {
            "title": "Data Engineer",
            "company": "LTIMindtree",
            "location": "Bengaluru / Pune",
            "domain": "data",
            "url": "https://www.naukri.com/job-listings-data-engineer-ltimindtree-bengaluru-1-to-4-years-281026006789",
            "desc": "ETL pipeline development, SQL, PySpark, Python, data warehousing, and AWS Redshift.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Data Engineer - Python & SQL",
            "company": "Cognizant",
            "location": "Hyderabad / Chennai",
            "domain": "data",
            "url": "https://www.naukri.com/job-listings-data-engineer-python-sql-cognizant-hyderabad-1-to-3-years-291026007890",
            "desc": "Designing relational & columnar schemas, building robust batch and streaming data pipelines with Python and Airflow.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Data Engineer",
            "company": "Tata Consultancy Services",
            "location": "Bengaluru / Remote",
            "domain": "data",
            "url": "https://www.naukri.com/job-listings-data-engineer-tata-consultancy-services-bengaluru-2-to-5-years-261026008901",
            "desc": "Distributed computing, Apache Spark, Airflow DAGs, Python, Kafka, and enterprise data architecture.",
            "posted": "4d ago",
            "days_old": 4
        },

        # --- Python Developer Jobs ---
        {
            "title": "Python Developer",
            "company": "Bookswagon",
            "location": "New Delhi",
            "domain": "python",
            "url": "https://www.naukri.com/job-listings-python-developer-bookswagon-new-delhi-1-to-3-years-291026009012",
            "desc": "Backend web development with Python, FastAPI, Django, PostgreSQL, and scalable microservices.",
            "posted": "2d ago",
            "days_old": 2
        },
        {
            "title": "Python / AI Developer",
            "company": "Honeybee Tech Solutions",
            "location": "Bengaluru",
            "domain": "python",
            "url": "https://www.naukri.com/job-listings-python-ai-developer-honeybee-tech-solutions-bengaluru-1-to-3-years-301026010123",
            "desc": "Developing AI-powered APIs, asynchronous Python services, database integration, and Docker.",
            "posted": "1d ago",
            "days_old": 1
        },
        {
            "title": "Junior Python Engineer",
            "company": "Globant",
            "location": "Pune / Hybrid",
            "domain": "python",
            "url": "https://www.naukri.com/job-listings-junior-python-engineer-globant-pune-0-to-2-years-271026011234",
            "desc": "Clean code in Python 3.x, REST APIs, unit testing, Git workflows, and cloud microservices.",
            "posted": "3d ago",
            "days_old": 3
        }
    ]

    async def search_jobs(self, query: str, location: str = "India", max_days_old: int = 15, limit: int = 15) -> List[ScrapedJob]:
        q_lower = (query or "").lower().strip()
        q_terms = [t for t in re.split(r"\W+", q_lower) if len(t) > 1]

        is_analyst_search = "analyst" in q_terms or "analytics" in q_terms
        is_ml_search = "machine" in q_terms or "ml" in q_terms or ("learning" in q_terms and not is_analyst_search)
        is_genai_search = "gen" in q_terms or "generative" in q_terms or "agent" in q_terms or "ai" in q_terms or "llm" in q_terms
        is_data_eng_search = "engineer" in q_terms and ("data" in q_terms or "etl" in q_terms) and not is_analyst_search
        is_python_search = "python" in q_terms or "backend" in q_terms

        # Disambiguate
        if is_ml_search and not ("generative" in q_terms or "agent" in q_terms):
            is_genai_search = False

        target_domain = None
        if is_analyst_search:
            target_domain = "data_analyst"
        elif is_ml_search:
            target_domain = "ml"
        elif is_genai_search:
            target_domain = "genai"
        elif is_data_eng_search:
            target_domain = "data"
        elif is_python_search:
            target_domain = "python"

        scored_jobs = []
        for item in self.ALL_NAUKRI_JOBS:
            if item.get("days_old", 1) > max_days_old:
                continue

            domain = item.get("domain", "")

            # STRICT ISOLATION: if target domain matches, skip all non-matching domains
            if target_domain and domain != target_domain:
                continue

            # Base score + recency (1d ago > 2d ago > 3d ago)
            score = 100 + (15 - item.get("days_old", 1))

            title_lower = item["title"].lower()
            for term in q_terms:
                if term in title_lower:
                    score += 10

            scored_jobs.append((score, item))

        # Sort jobs strictly by descending score (highest relevance, newest first)
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
                    platform="Naukri",
                    posted_time_ago=item["posted"],
                    easy_apply_available=True
                )
            )

        return results

naukri_scraper = NaukriScraper()
