import os
import re
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from app.config import settings

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
MEMORY_FILE = os.path.join(DATA_DIR, "qa_memory.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending_questions.json")

STOP_WORDS = {
    "what", "is", "your", "how", "many", "do", "you", "have", "with", "the", "in", "for",
    "please", "specify", "years", "experience", "rate", "scale", "tell", "about", "give",
    "briefly", "describe", "worked", "working", "any", "and", "per", "annum", "lacs", "level"
}

def extract_distinctive_keywords(text: str) -> List[str]:
    words = [w for w in re.split(r"\W+", (text or "").lower()) if len(w) > 2 and w not in STOP_WORDS]
    return words

# Default verified candidate facts from Sachin Sharma's profile & resume
DEFAULT_MEMORIES = [
    {
        "id": "full_name",
        "question": "What is your full name?",
        "keywords": ["full name", "your name", "candidate name", "first name", "last name"],
        "answer": "Sachin Sharma",
        "category": "personal"
    },
    {
        "id": "mobile_phone",
        "question": "What is your mobile/contact number?",
        "keywords": ["mobile", "phone", "contact number", "whatsapp", "reach you"],
        "answer": "6378046617",
        "category": "contact"
    },
    {
        "id": "email_address",
        "question": "What is your email address?",
        "keywords": ["email", "e-mail", "mail address"],
        "answer": "sachin.sharma.coder@gmail.com",
        "category": "contact"
    },
    {
        "id": "current_ctc",
        "question": "What is your current CTC in Lacs per annum?",
        "keywords": ["current ctc", "current salary", "present ctc", "present salary", "existing ctc"],
        "answer": "7",
        "category": "compensation"
    },
    {
        "id": "expected_ctc",
        "question": "What is your expected CTC in Lacs per annum?",
        "keywords": ["expected ctc", "expected salary", "salary expectation"],
        "answer": "10",
        "category": "compensation"
    },
    {
        "id": "notice_period",
        "question": "What is your notice period / joining time?",
        "keywords": ["notice period", "days to join", "how soon", "available to join", "joining time"],
        "answer": "15 Days or less",
        "category": "availability"
    },
    {
        "id": "total_experience",
        "question": "How many total years of work experience do you have?",
        "keywords": ["total experience", "overall experience", "total years", "years of experience"],
        "answer": "2",
        "category": "experience"
    },
    {
        "id": "current_location",
        "question": "What is your current city / location?",
        "keywords": ["current location", "current city", "where are you located", "where do you live", "current address"],
        "answer": "Bengaluru",
        "category": "location"
    },
    {
        "id": "willing_relocate",
        "question": "Are you willing to relocate?",
        "keywords": ["relocate", "relocation", "willing to move"],
        "answer": "Yes",
        "category": "location"
    },
    {
        "id": "highest_education",
        "question": "What is your highest qualification / degree?",
        "keywords": ["highest qualification", "degree", "highest education", "graduation", "undergraduate"],
        "answer": "B.Tech in Computer Science and Engineering",
        "category": "education"
    },
    {
        "id": "ssc_10th",
        "question": "Please specify your percentage in S.S.C (10th Standard)?",
        "keywords": ["s.s.c", "10th standard", "10th percentage", "ssc marks"],
        "answer": "Between 80% to 90%",
        "category": "education"
    },
    {
        "id": "hsc_12th",
        "question": "Please specify your percentage in H.S.C (12th Standard)/Diploma?",
        "keywords": ["h.s.c", "12th standard", "12th percentage", "hsc marks"],
        "answer": "Between 80% to 90%",
        "category": "education"
    },
    {
        "id": "english_rating",
        "question": "How would you rate your English Communication skills?",
        "keywords": ["english communication", "communication skill", "english proficiency"],
        "answer": "5",
        "category": "skills"
    },
    {
        "id": "skills_technologies",
        "question": "What skills and technologies have you worked with?",
        "keywords": ["skills and technologies", "tech stack", "tools have you worked", "technical skills"],
        "answer": "Python, FastAPI, LangChain, LangGraph, Generative AI, RAG, Autonomous Agents, LLMs, Docker, PyTorch, SQL, Vector Databases (ChromaDB)",
        "category": "skills"
    },
    {
        "id": "agentic_workflows",
        "question": "Have you worked on agentic workflows, context-engineering or AI applications?",
        "keywords": ["agentic workflows", "agentic", "context-engineering", "autonomous agents", "langgraph"],
        "answer": "Yes. I designed autonomous agents and multi-agent workflows using LangGraph and LangChain, focusing on context engineering, tool-calling, and RAG optimization for production AI applications.",
        "category": "skills"
    },
    {
        "id": "exp_python",
        "question": "How many years of experience in Python?",
        "keywords": ["experience in python", "experience do you have in python", "years in python"],
        "answer": "2",
        "category": "experience"
    },
    {
        "id": "exp_sql",
        "question": "How many years of experience in SQL?",
        "keywords": ["experience in sql", "experience do you have in sql", "years in sql"],
        "answer": "2",
        "category": "experience"
    },
    {
        "id": "exp_pandas",
        "question": "How many years of experience in Pandas?",
        "keywords": ["experience in pandas", "experience do you have in pandas", "years in pandas"],
        "answer": "2",
        "category": "experience"
    },
    {
        "id": "exp_etl",
        "question": "How many years of experience in ETL Development?",
        "keywords": ["experience in etl", "experience do you have in etl", "etl development"],
        "answer": "2",
        "category": "experience"
    }
]

class QAMemoryVault:
    """
    Persistent memory vault for recruiter screening questions and candidate answers.
    - If question is known in memory -> returns verified answer.
    - If question is UNKNOWN -> does NOT make up answers; prompts user (via Telegram & UI),
      waits for user reply, and saves the answer permanently to memory.
    """
    def __init__(self):
        self._memories: List[Dict] = []
        self._pending_questions: Dict[str, Dict] = {} # question_id -> question details
        self._waiting_events: Dict[str, asyncio.Event] = {} # question_id -> Event
        self._load()
        self._load_pending()

    def _load(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._memories = data.get("memories", [])
            except Exception as e:
                print(f"[QA Vault] Load error: {e}, using defaults.")
                self._memories = list(DEFAULT_MEMORIES)
        else:
            self._memories = list(DEFAULT_MEMORIES)
            self._save()

    def _save(self):
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({"memories": self._memories, "updated_at": datetime.now().isoformat()}, f, indent=2)
        except Exception as e:
            print(f"[QA Vault] Save error: {e}")

    def _load_pending(self):
        if os.path.exists(PENDING_FILE):
            try:
                with open(PENDING_FILE, "r", encoding="utf-8") as f:
                    self._pending_questions = json.load(f)
            except Exception as e:
                print(f"[QA Vault] Pending load error: {e}")
                self._pending_questions = {}
        else:
            self._pending_questions = {}

    def _save_pending(self):
        try:
            with open(PENDING_FILE, "w", encoding="utf-8") as f:
                json.dump(self._pending_questions, f, indent=2)
        except Exception as e:
            print(f"[QA Vault] Pending save error: {e}")

    def get_all_memories(self) -> List[Dict]:
        return self._memories

    def get_pending_questions(self) -> List[Dict]:
        self._load_pending()
        return list(self._pending_questions.values())

    def learn(self, question: str, answer: str, category: str = "custom") -> Dict:
        """
        Learns and persists a new question & answer pair permanently.
        """
        clean_q = question.strip()
        clean_ans = answer.strip()
        q_id = re.sub(r"[^a-zA-Z0-9]+", "_", clean_q.lower())[:40].strip("_")

        # Check if already exists; if so, update answer
        for item in self._memories:
            if item.get("id") == q_id or item.get("question", "").lower() == clean_q.lower():
                item["answer"] = clean_ans
                item["updated_at"] = datetime.now().isoformat()
                self._save()
                self._resolve_pending_event(clean_q, clean_ans)
                print(f"[QA Vault] Updated existing Q&A: '{clean_q}' -> '{clean_ans}'")
                return item

        distinct_kw = extract_distinctive_keywords(clean_q)
        new_entry = {
            "id": q_id,
            "question": clean_q,
            "keywords": distinct_kw[:6],
            "answer": clean_ans,
            "category": category,
            "learned_at": datetime.now().isoformat()
        }
        self._memories.append(new_entry)
        self._save()
        self._resolve_pending_event(clean_q, clean_ans)
        print(f"[QA Vault] Successfully learned new Q&A: '{clean_q}' -> '{clean_ans}'")
        return new_entry

    def delete_memory(self, memory_id: str) -> bool:
        initial_len = len(self._memories)
        self._memories = [m for m in self._memories if m.get("id") != memory_id]
        if len(self._memories) < initial_len:
            self._save()
            return True
        return False

    def find_answer(self, question: str) -> Optional[str]:
        """
        Looks up an answer from memory using exact match and keyword heuristics.
        Returns None if not found (strictly avoids hallucinating).
        """
        if not question:
            return None

        q_clean = question.lower().strip()

        # 1. Exact or substring match in stored question
        for item in self._memories:
            stored_q = item.get("question", "").lower()
            if stored_q and (stored_q in q_clean or q_clean in stored_q):
                return item.get("answer")

        # 2. Distinctive Keyword matching (filtered with STOP_WORDS)
        q_distinct = set(extract_distinctive_keywords(q_clean))
        if q_distinct:
            best_match = None
            max_matches = 0
            for item in self._memories:
                item_kw = set(item.get("keywords", []))
                item_distinct = set(extract_distinctive_keywords(item.get("question", "")))
                combined = item_kw.union(item_distinct)
                overlap = len(q_distinct.intersection(combined))

                # Require at least 2 distinctive words overlap, or 100% of distinctive words if short
                min_required = 1 if len(q_distinct) == 1 else 2
                if overlap >= min_required and overlap > max_matches:
                    max_matches = overlap
                    best_match = item

            if best_match:
                return best_match.get("answer")

        # 3. Specific pattern rules for standard HR questions
        if any(w in q_clean for w in ["current ctc", "current salary", "present ctc"]):
            return "7"
        if any(w in q_clean for w in ["expected ctc", "expected salary"]):
            return "10"
        if any(w in q_clean for w in ["notice period", "days to join", "how soon"]):
            return "15 Days or less"
        if any(w in q_clean for w in ["mobile", "phone number", "whatsapp number"]):
            return "6378046617"
        if "email" in q_clean:
            return "sachin.sharma.coder@gmail.com"
        if any(w in q_clean for w in ["total experience", "overall experience"]):
            return "2"
        if any(w in q_clean for w in ["current location", "current city"]):
            return "Bengaluru"
        if any(w in q_clean for w in ["relocate", "relocation"]):
            return "Yes"

        return None

    def register_pending_question(self, question: str, job_title: str, company: str, job_url: str, options: List[str] = None) -> str:
        """
        Registers an unanswered question into the pending queue and prepares an async wait event.
        """
        self._load_pending()
        q_id = re.sub(r"[^a-zA-Z0-9]+", "_", question.lower())[:30].strip("_")
        entry = {
            "id": q_id,
            "question": question,
            "job_title": job_title,
            "company": company,
            "job_url": job_url,
            "options": options or [],
            "asked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }
        self._pending_questions[q_id] = entry
        self._save_pending()
        if q_id not in self._waiting_events:
            self._waiting_events[q_id] = asyncio.Event()
        return q_id

    def _resolve_pending_event(self, question: str, answer: str):
        """Wakes up any coroutine waiting for an answer to this question and updates disk storage."""
        self._load_pending()
        matched_id = None
        for q_id, item in list(self._pending_questions.items()):
            if item.get("status") == "pending":
                if item["question"].lower() in question.lower() or question.lower() in item["question"].lower():
                    matched_id = q_id
                    item["status"] = "answered"
                    item["answer"] = answer
                    break

        # If no specific string match, resolve the latest pending item
        if not matched_id:
            pending_ids = [k for k, v in self._pending_questions.items() if v.get("status") == "pending"]
            if pending_ids:
                matched_id = pending_ids[-1]
                self._pending_questions[matched_id]["status"] = "answered"
                self._pending_questions[matched_id]["answer"] = answer

        self._save_pending()

        if matched_id and matched_id in self._waiting_events:
            self._waiting_events[matched_id].set()

    def skip_pending_question(self, q_id: str) -> bool:
        """Marks a pending question as skipped/dismissed and resolves any waiting coroutine."""
        self._load_pending()
        if q_id in self._pending_questions:
            self._pending_questions[q_id]["status"] = "skipped"
            self._save_pending()
            if q_id in self._waiting_events:
                self._waiting_events[q_id].set()
            print(f"[QA Vault] Pending question '{q_id}' skipped by user.")
            return True
        return False

    async def wait_for_user_answer(self, q_id: str, timeout_seconds: int = 35) -> Optional[str]:
        """
        Waits for the user to answer via Telegram or Web UI.
        Returns the user's answer if provided within timeout, else None.
        """
        if q_id not in self._waiting_events:
            self._waiting_events[q_id] = asyncio.Event()

        event = self._waiting_events[q_id]

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            self._load_pending()
            pending_item = self._pending_questions.get(q_id)
            if pending_item and pending_item.get("answer"):
                return pending_item["answer"]
        except asyncio.TimeoutError:
            pass

        return None

qa_vault = QAMemoryVault()
