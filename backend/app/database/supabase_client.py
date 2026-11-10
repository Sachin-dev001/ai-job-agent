import os
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger("supabase_client")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"
PROFILES_FILE = DATA_DIR / "user_profiles.json"
USERS_FILE = DATA_DIR / "users.json"
APPLICATIONS_FILE = DATA_DIR / "applications.json"

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_ANON_KEY", ""))

_supabase_client = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("[Supabase] Cloud client initialized successfully.")
    except Exception as e:
        logger.warning(f"[Supabase] Could not initialize cloud client: {e}. Falling back to local storage.")
else:
    logger.info("[Supabase] Operating in local storage mode.")

def is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError):
        return False

class CloudDatabaseService:
    """
    Unified database service supporting both Supabase Cloud PostgreSQL
    and local persistent storage fallback for offline development.
    """

    def is_cloud_enabled(self) -> bool:
        return _supabase_client is not None

    def _load_local_profiles(self) -> Dict[str, Any]:
        if PROFILES_FILE.exists():
            try:
                with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"[Supabase] Error reading local profiles: {e}")
        return {}

    def _save_local_profiles(self, profiles: Dict[str, Any]):
        try:
            import tempfile
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=DATA_DIR, delete=False, encoding="utf-8") as tf:
                json.dump(profiles, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, PROFILES_FILE)
        except Exception as e:
            logger.warning(f"[Supabase] Error saving local profiles: {e}")

    def _load_local_users(self) -> Dict[str, Any]:
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"[Supabase] Error reading local users: {e}")
        return {}

    def _save_local_users(self, users: Dict[str, Any]):
        try:
            import tempfile
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=DATA_DIR, delete=False, encoding="utf-8") as tf:
                json.dump(users, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, USERS_FILE)
        except Exception as e:
            logger.warning(f"[Supabase] Error saving local users: {e}")

    def _load_local_applications(self) -> Dict[str, List[Dict[str, Any]]]:
        if APPLICATIONS_FILE.exists():
            try:
                with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"[Supabase] Error reading local applications: {e}")
        return {}

    def _save_local_applications(self, apps: Dict[str, List[Dict[str, Any]]]):
        try:
            import tempfile
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=DATA_DIR, delete=False, encoding="utf-8") as tf:
                json.dump(apps, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, APPLICATIONS_FILE)
        except Exception as e:
            logger.warning(f"[Supabase] Error saving local applications: {e}")

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        norm_email = (email or "").strip().lower()
        if not norm_email:
            return None
        users = self._load_local_users()
        for u in users.values():
            if u.get("email", "").lower() == norm_email:
                return u
        return None

    async def create_user(self, email: str, password_hash: str, full_name: str, user_id: str) -> Dict[str, Any]:
        users = self._load_local_users()
        user_record = {
            "id": user_id,
            "email": email.strip().lower(),
            "full_name": full_name.strip(),
            "name": full_name.strip(),
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        }
        users[user_id] = user_record
        self._save_local_users(users)
        await self.update_profile(user_id, {
            "full_name": full_name.strip(),
            "email": email.strip().lower()
        })
        return user_record

    # --------------------------------------------------------------------------
    # User Profile Operations
    # --------------------------------------------------------------------------
    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                res = _supabase_client.table("profiles").select("*").eq("id", user_id).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"[Supabase] Error getting profile for {user_id}: {e}")

        # Local storage check
        local_profiles = self._load_local_profiles()
        if user_id in local_profiles:
            return local_profiles[user_id]

        # Isolated candidate profile fallback (never leak private contact details across users)
        return {
            "id": user_id,
            "full_name": "Candidate",
            "email": f"{user_id}@candidate.autoapply.ai" if user_id != "guest-candidate" else "guest@autoapply.ai",
            "phone": "",
            "current_ctc": "",
            "expected_ctc": "",
            "notice_period": "",
            "resume_analyzed": False
        }

    async def update_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                updates_copy = dict(updates)
                updates_copy["updated_at"] = datetime.utcnow().isoformat()
                _supabase_client.table("profiles").update(updates_copy).eq("id", user_id).execute()
            except Exception as e:
                logger.error(f"[Supabase] Error updating profile for {user_id}: {e}")

        # Always save locally so local testing and offline modes retain user profiles
        local_profiles = self._load_local_profiles()
        current = local_profiles.get(user_id, {
            "id": user_id,
            "full_name": "Candidate",
            "email": f"{user_id}@candidate.autoapply.ai" if user_id != "guest-candidate" else "guest@autoapply.ai",
            "resume_analyzed": False
        })
        current.update(updates)
        current["updated_at"] = datetime.utcnow().isoformat()
        local_profiles[user_id] = current
        self._save_local_profiles(local_profiles)
        return True

    # --------------------------------------------------------------------------
    # Q&A Memory Vault Operations
    # --------------------------------------------------------------------------
    async def get_memories(self, user_id: str) -> List[Dict[str, Any]]:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                res = _supabase_client.table("qa_memory").select("*").eq("user_id", user_id).order("learned_at", desc=True).execute()
                return res.data or []
            except Exception as e:
                logger.error(f"[Supabase] Error getting memories for {user_id}: {e}")
        from app.memory.qa_vault import qa_vault
        return qa_vault.get_user_memories(user_id=user_id)

    async def save_memory(self, user_id: str, question: str, answer: str, category: str = "custom", keywords: List[str] = None) -> Dict[str, Any]:
        keywords = keywords or []
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                payload = {
                    "user_id": user_id,
                    "question": question,
                    "answer": answer,
                    "category": category,
                    "keywords": keywords,
                    "learned_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                res = _supabase_client.table("qa_memory").insert(payload).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"[Supabase] Error saving memory for {user_id}: {e}")
        from app.memory.qa_vault import qa_vault
        return qa_vault.learn(question=question, answer=answer, category=category, user_id=user_id)

    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                _supabase_client.table("qa_memory").delete().eq("id", memory_id).eq("user_id", user_id).execute()
                return True
            except Exception as e:
                logger.error(f"[Supabase] Error deleting memory {memory_id}: {e}")
                return False
        from app.memory.qa_vault import qa_vault
        return qa_vault.delete_memory(memory_id=memory_id, user_id=user_id)

    # --------------------------------------------------------------------------
    # Job Application Tracker Operations
    # --------------------------------------------------------------------------
    async def get_applications(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                res = _supabase_client.table("job_applications").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
                if res.data is not None:
                    return res.data
            except Exception as e:
                logger.error(f"[Supabase] Error getting applications for {user_id}: {e}")
        apps_map = self._load_local_applications()
        user_apps = apps_map.get(user_id, [])
        return user_apps[:limit]

    async def create_application(self, user_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        app_item = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "platform": job_data.get("platform", "wellfound"),
            "job_title": job_data.get("job_title", "Software Engineer"),
            "company_name": job_data.get("company_name", "Tech Startup"),
            "job_url": job_data.get("job_url", ""),
            "status": job_data.get("status", "applied"),
            "match_score": job_data.get("match_score", 90.0),
            "proof_url": job_data.get("proof_url"),
            "created_at": datetime.utcnow().isoformat()
        }
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                res = _supabase_client.table("job_applications").insert(app_item).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"[Supabase] Error creating cloud application: {e}")

        apps_map = self._load_local_applications()
        if user_id not in apps_map:
            apps_map[user_id] = []
        apps_map[user_id].insert(0, app_item)
        self._save_local_applications(apps_map)
        return app_item

    async def update_application_status(self, user_id: str, app_id: str, status: str, proof_url: str = None, error: str = None) -> bool:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                updates = {"status": status}
                if status == "applied":
                    updates["applied_at"] = datetime.utcnow().isoformat()
                if proof_url:
                    updates["proof_screenshot_url"] = proof_url
                if error:
                    updates["error_message"] = error
                _supabase_client.table("job_applications").update(updates).eq("id", app_id).eq("user_id", user_id).execute()
                return True
            except Exception as e:
                logger.error(f"[Supabase] Error updating application status: {e}")
                return False
        return True

    # --------------------------------------------------------------------------
    # Cloud Storage (Resumes and Screenshots)
    # --------------------------------------------------------------------------
    async def upload_proof_screenshot(self, user_id: str, filename: str, local_path: str) -> Optional[str]:
        if not os.path.exists(local_path):
            return None
        if self.is_cloud_enabled():
            try:
                storage_path = f"{user_id}/{filename}"
                with open(local_path, "rb") as f:
                    _supabase_client.storage.from_("proofs").upload(storage_path, f, {"content-type": "image/png", "upsert": "true"})
                public_url = _supabase_client.storage.from_("proofs").get_public_url(storage_path)
                return public_url
            except Exception as e:
                logger.warning(f"[Supabase Storage] Could not upload proof to bucket: {e}")
        return f"/proofs/{os.path.basename(local_path)}"

cloud_db = CloudDatabaseService()
