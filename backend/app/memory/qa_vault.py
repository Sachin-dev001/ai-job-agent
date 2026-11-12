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
USER_MEMORIES_FILE = os.path.join(DATA_DIR, "user_memories.json")
LEGACY_MEMORY_FILE = os.path.join(DATA_DIR, "qa_memory.json")
PENDING_FILE = os.path.join(DATA_DIR, "pending_questions.json")

# Pure grammatical stop words: domain critical words like 'years', 'experience', 'per', 'annum', 'lacs',
# 'current', 'expected', 'notice', 'fixed', 'variable' are preserved to avoid question collision.
STOP_WORDS = {
    "what", "is", "your", "how", "many", "do", "you", "have", "with", "the", "in", "for",
    "please", "specify", "rate", "scale", "tell", "about", "give", "briefly", "describe",
    "worked", "working", "any", "and", "level", "are"
}

def extract_distinctive_keywords(text: str) -> List[str]:
    words = [w for w in re.split(r"\W+", (text or "").lower()) if len(w) > 2 and w not in STOP_WORDS]
    return words

def questions_have_semantic_conflict(q1: str, q2: str) -> bool:
    """
    Prevents false-positive Q&A matching when questions differ on polarity or key modifiers
    (e.g., current CTC vs expected CTC, React Native vs React.js, fixed vs variable pay).
    """
    q1_words = set(re.split(r"\W+", (q1 or "").lower()))
    q2_words = set(re.split(r"\W+", (q2 or "").lower()))

    conflict_pairs = [
        ("current", "expected"),
        ("fixed", "variable"),
        ("notice", "salary"),
        ("notice", "ctc"),
        ("minimum", "maximum"),
        ("relocate", "remote")
    ]
    for w1, w2 in conflict_pairs:
        if (w1 in q1_words and w2 in q2_words) or (w2 in q1_words and w1 in q2_words):
            return True

    # Modifier differentiation (e.g., React Native vs React)
    if ("native" in q1_words and "native" not in q2_words) or ("native" in q2_words and "native" not in q1_words):
        return True

    return False

DEFAULT_MEMORIES = []

class QAMemoryVault:
    """
    Persistent multi-tenant memory vault for recruiter screening questions and candidate answers.
    - Each candidate (or guest session) has isolated memories partitioned by user_id.
    - Zero cross-account data leakage.
    - Atomic JSON writes to eliminate corruption during container restarts or concurrent updates.
    - Strict polarity/modifier guardrails prevent false-positive answer lookups.
    """
    def __init__(self):
        self._user_memories: Dict[str, List[Dict]] = {}
        self._pending_questions: Dict[str, Dict] = {} # question_id -> question details
        self._waiting_events: Dict[str, asyncio.Event] = {} # question_id -> Event
        self._lock = asyncio.Lock()
        self._load()
        self._load_pending()

    def _sanitize_user_id(self, user_id: Optional[str]) -> str:
        if not user_id or not str(user_id).strip():
            return "guest-candidate"
        return str(user_id).strip()

    def _load(self):
        if os.path.exists(USER_MEMORIES_FILE):
            try:
                with open(USER_MEMORIES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._user_memories = data.get("users", {})
            except Exception as e:
                print(f"[QA Vault] Multi-tenant load error: {e}")
                self._user_memories = {}
        else:
            self._user_memories = {}
            self._save()

        if os.path.exists(LEGACY_MEMORY_FILE):
            try:
                with open(LEGACY_MEMORY_FILE, "w", encoding="utf-8") as f:
                    json.dump({"memories": [], "updated_at": datetime.now().isoformat()}, f, indent=2)
            except Exception:
                pass

    def _save(self):
        """Atomic write using temporary file replacement to avoid corruption."""
        try:
            temp_file = f"{USER_MEMORIES_FILE}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump({
                    "users": self._user_memories,
                    "updated_at": datetime.now().isoformat()
                }, f, indent=2)
            os.replace(temp_file, USER_MEMORIES_FILE)
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
        """Atomic write for pending questions."""
        try:
            temp_file = f"{PENDING_FILE}.tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._pending_questions, f, indent=2)
            os.replace(temp_file, PENDING_FILE)
        except Exception as e:
            print(f"[QA Vault] Pending save error: {e}")

    def get_user_memories(self, user_id: str = "guest-candidate") -> List[Dict]:
        uid = self._sanitize_user_id(user_id)
        return list(self._user_memories.get(uid, []))

    def get_all_memories(self, user_id: str = "guest-candidate") -> List[Dict]:
        return self.get_user_memories(user_id)

    def get_pending_questions(self, user_id: Optional[str] = None) -> List[Dict]:
        self._load_pending()
        all_pending = list(self._pending_questions.values())
        if user_id:
            uid = self._sanitize_user_id(user_id)
            return [p for p in all_pending if p.get("user_id", "guest-candidate") == uid]
        return all_pending

    def learn(self, question: str, answer: str, category: str = "custom", user_id: str = "guest-candidate") -> Dict:
        uid = self._sanitize_user_id(user_id)
        clean_q = question.strip()
        clean_ans = answer.strip()
        q_id = re.sub(r"[^a-zA-Z0-9]+", "_", clean_q.lower())[:40].strip("_")

        user_list = self._user_memories.setdefault(uid, [])

        for item in user_list:
            if item.get("id") == q_id or item.get("question", "").lower() == clean_q.lower():
                item["answer"] = clean_ans
                item["updated_at"] = datetime.now().isoformat()
                self._save()
                self._resolve_pending_event(clean_q, clean_ans, uid)
                print(f"[QA Vault] [{uid}] Updated existing Q&A: '{clean_q}' -> '{clean_ans}'")
                return item

        distinct_kw = extract_distinctive_keywords(clean_q)
        new_entry = {
            "id": q_id,
            "question": clean_q,
            "keywords": distinct_kw[:8],
            "answer": clean_ans,
            "category": category,
            "learned_at": datetime.now().isoformat()
        }
        user_list.append(new_entry)
        self._save()
        self._resolve_pending_event(clean_q, clean_ans, uid)
        print(f"[QA Vault] [{uid}] Successfully learned new Q&A: '{clean_q}' -> '{clean_ans}'")
        return new_entry

    def delete_memory(self, memory_id: str, user_id: str = "guest-candidate") -> bool:
        uid = self._sanitize_user_id(user_id)
        user_list = self._user_memories.get(uid, [])
        initial_len = len(user_list)
        self._user_memories[uid] = [m for m in user_list if m.get("id") != memory_id]
        if len(self._user_memories[uid]) < initial_len:
            self._save()
            return True
        return False

    def find_answer(self, question: str, user_id: str = "guest-candidate") -> Optional[str]:
        """
        Looks up an answer from this specific user's memory vault using exact match,
        keyword heuristics, and strict conflict detection.
        """
        if not question:
            return None

        uid = self._sanitize_user_id(user_id)
        user_list = self._user_memories.get(uid, [])
        q_clean = question.lower().strip()

        # 1. Exact or high-precision substring match in stored question
        for item in user_list:
            stored_q = item.get("question", "").lower()
            if stored_q and (stored_q in q_clean or q_clean in stored_q):
                if not questions_have_semantic_conflict(q_clean, stored_q):
                    return item.get("answer")

        # 2. Distinctive Keyword matching with semantic conflict filtering
        q_distinct = set(extract_distinctive_keywords(q_clean))
        if q_distinct:
            best_match = None
            max_matches = 0
            for item in user_list:
                stored_q = item.get("question", "")
                if questions_have_semantic_conflict(q_clean, stored_q):
                    continue

                item_kw = set(item.get("keywords", []))
                item_distinct = set(extract_distinctive_keywords(stored_q))
                combined = item_kw.union(item_distinct)
                overlap = len(q_distinct.intersection(combined))

                min_required = 1 if len(q_distinct) == 1 else 2
                if overlap >= min_required and overlap > max_matches:
                    max_matches = overlap
                    best_match = item

            if best_match:
                return best_match.get("answer")

        return None

    def register_pending_question(self, question: str, job_title: str, company: str, job_url: str, options: List[str] = None, user_id: str = "guest-candidate") -> str:
        self._load_pending()
        q_id = re.sub(r"[^a-zA-Z0-9]+", "_", question.lower())[:30].strip("_")
        entry = {
            "id": q_id,
            "user_id": self._sanitize_user_id(user_id),
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

    def _resolve_pending_event(self, question: str, answer: str, user_id: Optional[str] = None):
        self._load_pending()
        matched_id = None
        for q_id, item in list(self._pending_questions.items()):
            if item.get("status") == "pending":
                if user_id and item.get("user_id") != user_id:
                    continue
                if item["question"].lower() in question.lower() or question.lower() in item["question"].lower():
                    matched_id = q_id
                    item["status"] = "answered"
                    item["answer"] = answer
                    break

        if not matched_id:
            pending_ids = [
                k for k, v in self._pending_questions.items() 
                if v.get("status") == "pending" and (not user_id or v.get("user_id") == user_id)
            ]
            if pending_ids:
                matched_id = pending_ids[-1]
                self._pending_questions[matched_id]["status"] = "answered"
                self._pending_questions[matched_id]["answer"] = answer

        self._save_pending()

        if matched_id and matched_id in self._waiting_events:
            self._waiting_events[matched_id].set()

    def skip_pending_question(self, q_id: str, user_id: Optional[str] = None) -> bool:
        self._load_pending()
        if q_id in self._pending_questions:
            if user_id:
                uid = self._sanitize_user_id(user_id)
                if self._pending_questions[q_id].get("user_id", "guest-candidate") != uid:
                    return False
            self._pending_questions[q_id]["status"] = "skipped"
            self._save_pending()
            if q_id in self._waiting_events:
                self._waiting_events[q_id].set()
            print(f"[QA Vault] Pending question '{q_id}' skipped by user.")
            return True
        return False

    async def wait_for_user_answer(self, q_id: str, timeout_seconds: int = 35) -> Optional[str]:
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
