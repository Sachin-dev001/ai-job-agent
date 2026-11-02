import os
import json
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger("supabase_client")

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
        return {
            "id": user_id,
            "full_name": "Sachin Sharma",
            "email": "sachin.sharma.coder@gmail.com",
            "phone": "6378046617",
            "current_ctc": "7 LPA",
            "expected_ctc": "10 LPA",
            "notice_period": "15 Days"
        }

    async def update_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                updates["updated_at"] = datetime.utcnow().isoformat()
                _supabase_client.table("profiles").update(updates).eq("id", user_id).execute()
                return True
            except Exception as e:
                logger.error(f"[Supabase] Error updating profile for {user_id}: {e}")
                return False
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
        return qa_vault.get_all_memories()

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
        return qa_vault.learn(question=question, answer=answer, category=category)

    async def delete_memory(self, user_id: str, memory_id: str) -> bool:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                _supabase_client.table("qa_memory").delete().eq("id", memory_id).eq("user_id", user_id).execute()
                return True
            except Exception as e:
                logger.error(f"[Supabase] Error deleting memory {memory_id}: {e}")
                return False
        from app.memory.qa_vault import qa_vault
        return qa_vault.delete_memory(memory_id)

    # --------------------------------------------------------------------------
    # Job Application Tracker Operations
    # --------------------------------------------------------------------------
    async def get_applications(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                res = _supabase_client.table("job_applications").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
                return res.data or []
            except Exception as e:
                logger.error(f"[Supabase] Error getting applications for {user_id}: {e}")
        return []

    async def create_application(self, user_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        if self.is_cloud_enabled() and is_valid_uuid(user_id):
            try:
                payload = {
                    "user_id": user_id,
                    "platform": job_data.get("platform", "wellfound"),
                    "job_title": job_data.get("job_title", "Software Engineer"),
                    "company_name": job_data.get("company_name", "Tech Startup"),
                    "job_url": job_data.get("job_url", ""),
                    "status": job_data.get("status", "in_progress"),
                    "match_score": job_data.get("match_score", 90.0)
                }
                res = _supabase_client.table("job_applications").insert(payload).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                logger.error(f"[Supabase] Error creating application: {e}")
        return job_data

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
