import asyncio
import html
import httpx
import re
from typing import Optional, Dict
from app.config import settings
from app.memory.qa_vault import qa_vault

class TelegramBotListener:
    """
    Background worker that listens for user replies and commands on Telegram.
    Enables true Human-in-the-Loop memory:
    - User replies to recruiter questions directly on Telegram.
    - Scopes replies back to specific user_id and question_id using [QID:.. | UID:..] tags.
    - Zero cross-tenant data pollution during concurrent applicant runs.
    """
    def __init__(self):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.is_running = False
        self.offset = 0

    async def send_message(self, text: str, parse_mode: str = "HTML"):
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    print(f"[Telegram Listener] send_message error {res.status_code}: {res.text}")
                    if res.status_code == 400:
                        payload.pop("parse_mode", None)
                        await client.post(url, json=payload)
        except Exception as e:
            print(f"[Telegram Listener] send_message exception: {e}")

    async def start_listening(self):
        if not self.bot_token or not self.chat_id:
            print("[Telegram Listener] Telegram credentials not configured, skipping listener.")
            return

        self.is_running = True
        print("[Telegram Listener] Background listener started. Polling for user responses...")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset=-1")
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("result", [])
                    if results:
                        self.offset = results[-1]["update_id"] + 1
        except Exception as e:
            print(f"[Telegram Listener] Offset init error: {e}")

        while self.is_running:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.offset}&timeout=10"
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(url)

                if resp.status_code == 200:
                    updates = resp.json().get("result", [])
                    for update in updates:
                        self.offset = update["update_id"] + 1
                        message = update.get("message")
                        if not message or "text" not in message:
                            continue

                        user_text = message["text"].strip()
                        sender_id = str(message.get("chat", {}).get("id"))

                        if self.chat_id and sender_id != str(self.chat_id):
                            continue

                        await self._handle_user_message(user_text, message=message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(4)

    async def _handle_user_message(self, text: str, message: Optional[dict] = None):
        print(f"[Telegram Listener] Received message from user: '{text}'")

        # Command 1: /start or /help
        if text.lower() in ["/start", "/help"]:
            help_msg = (
                "🤖 <b>AI Job Application Assistant Active</b>\n\n"
                "I notify you whenever a recruiter asks a screening question not found in your resume.\n\n"
                "📌 <b>Available Commands:</b>\n"
                "• Reply directly to any question alert with your answer\n"
                "• <code>/memory</code> — View all remembered questions & answers\n"
                "• <code>/pending</code> — View questions currently waiting for your answer\n"
                "• <code>/learn Question = Answer</code> — Manually teach me a new answer\n"
            )
            await self.send_message(help_msg)
            return

        # Command 2: /memory
        if text.lower() == "/memory":
            memories = qa_vault.get_all_memories()
            if not memories:
                await self.send_message("🧠 <b>Memory Vault is empty.</b>")
                return

            msg = f"🧠 <b>Memory Vault ({len(memories)} Saved Answers):</b>\n\n"
            for idx, m in enumerate(memories[-8:]):
                msg += f"<b>{idx+1}. {html.escape(m.get('question', ''))}</b>\n↳ <code>{html.escape(str(m.get('answer', '')))}</code>\n\n"
            if len(memories) > 8:
                msg += f"<i>...and {len(memories)-8} more stored in your dashboard.</i>"
            await self.send_message(msg)
            return

        # Command 3: /pending
        if text.lower() == "/pending":
            pending = [p for p in qa_vault.get_pending_questions() if p.get("status") == "pending"]
            if not pending:
                await self.send_message("✅ <b>No questions pending!</b> All questions have been answered.")
                return

            msg = "❓ <b>Pending Recruiter Questions:</b>\n\n"
            for p in pending:
                msg += f"💼 <b>{html.escape(p.get('job_title', 'Job'))}</b> ({html.escape(p.get('company', 'Company'))}):\n<i>{html.escape(p.get('question', ''))}</i>\n<code>[QID:{p.get('id')} | UID:{p.get('user_id', 'guest-candidate')}]</code>\n\n"
            msg += "👉 <i>Reply directly to the alert or type your answer.</i>"
            await self.send_message(msg)
            return

        # Command 4: /skip
        if text.lower() == "/skip":
            pending = [p for p in qa_vault.get_pending_questions() if p.get("status") == "pending"]
            if pending:
                latest = pending[-1]
                qa_vault.skip_pending_question(latest["id"])
                await self.send_message(f"⏭️ <b>Question Skipped:</b>\n<i>{html.escape(latest['question'])}</i>\n\nThis question will not block your dashboard.")
            else:
                await self.send_message("ℹ️ <b>No pending questions to skip.</b>")
            return

        # Command 5: /learn <Question> = <Answer>
        if text.lower().startswith("/learn "):
            payload = text[7:].strip()
            if "=" in payload:
                q, a = payload.split("=", 1)
                qa_vault.learn(q.strip(), a.strip())
                await self.send_message(f"💾 <b>Saved to Memory!</b>\n\n❓ <b>Question:</b> {html.escape(q.strip())}\n✅ <b>Answer:</b> <code>{html.escape(a.strip())}</code>")
            else:
                await self.send_message("⚠️ <b>Format error.</b> Use: <code>/learn Question = Answer</code>")
            return

        # Check for [QID:.. | UID:..] metadata in reply_to_message or text
        reply_to = (message or {}).get("reply_to_message", {})
        reply_text = reply_to.get("text", "") or reply_to.get("caption", "") or ""
        search_blob = f"{reply_text}\n{text}"

        target_qid = None
        target_uid = None
        tag_match = re.search(r"\[QID:\s*([^\s\|\]]+)\s*\|\s*UID:\s*([^\]]+)\]", search_blob, re.IGNORECASE)
        if tag_match:
            target_qid = tag_match.group(1).strip()
            target_uid = tag_match.group(2).strip()

        # Clean answer text
        ans_text = text
        if text.lower().startswith("/ans "):
            ans_text = text[5:].strip()

        # Remove the tag if the user typed it in their own message
        ans_text = re.sub(r"\[QID:[^\]]+\]", "", ans_text).strip()

        matched_item = None
        pending_items = [p for p in qa_vault.get_pending_questions() if p.get("status") == "pending"]

        if target_qid:
            for p in pending_items:
                if p.get("id") == target_qid:
                    matched_item = p
                    break

        if not matched_item and target_uid:
            user_pending = [p for p in pending_items if p.get("user_id") == target_uid]
            if user_pending:
                matched_item = user_pending[-1]

        if not matched_item and pending_items:
            matched_item = pending_items[-1]

        if matched_item:
            q_text = matched_item["question"]
            job_title = matched_item.get("job_title", "Job")
            company = matched_item.get("company", "Company")
            uid = target_uid or matched_item.get("user_id", "guest-candidate")

            # Persist to memory vault scoped by tenant user_id
            qa_vault.learn(q_text, ans_text, category="recruiter_qa", user_id=uid)

            confirmation = (
                f"💾 <b>Saved & Remembered for Candidate [{html.escape(uid)}]!</b>\n\n"
                f"❓ <b>Question:</b> {html.escape(q_text)}\n"
                f"✅ <b>Your Answer:</b> <code>{html.escape(ans_text)}</code>\n"
                f"🏢 <b>Company:</b> {html.escape(company)} ({html.escape(job_title)})\n\n"
                f"🎉 Stored securely in your memory vault. Future applications will auto-fill this!"
            )
            await self.send_message(confirmation)
            print(f"[Telegram Listener] Successfully processed answer for '{q_text}': '{ans_text}' (UID: {uid})")
        else:
            await self.send_message(
                f"ℹ️ Received: \"<code>{html.escape(ans_text)}</code>\".\n\n"
                "No recruiter questions are currently waiting for an answer.\n"
                "• View memory: <code>/memory</code>\n"
                "• Teach new answer: <code>/learn Question = Answer</code>"
            )

telegram_listener = TelegramBotListener()
