import asyncio
import html
import httpx
from app.config import settings
from app.memory.qa_vault import qa_vault

class TelegramBotListener:
    """
    Background worker that listens for user replies and commands on Telegram.
    Enables true Human-in-the-Loop memory:
    - User replies to recruiter questions directly on Telegram.
    - Bot captures the answer and stores it permanently into qa_vault.
    - Notifies the user that the answer was saved.
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
                    # If HTML parsing failed, retry as clean plain text
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

        # Initialize offset to latest updates so old messages aren't reprocessed
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

                        # Verify message comes from authorized chat
                        if self.chat_id and sender_id != str(self.chat_id):
                            continue

                        await self._handle_user_message(user_text)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Brief sleep on network error before retrying
                await asyncio.sleep(4)

    async def _handle_user_message(self, text: str):
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
                msg += f"💼 <b>{html.escape(p.get('job_title', 'Job'))}</b> ({html.escape(p.get('company', 'Company'))}):\n<i>{html.escape(p.get('question', ''))}</i>\n\n"
            msg += "👉 <i>Simply type your answer to resolve the latest question.</i>"
            await self.send_message(msg)
            return

        # Command 4: /learn <Question> = <Answer>
        if text.lower().startswith("/learn "):
            payload = text[7:].strip()
            if "=" in payload:
                q, a = payload.split("=", 1)
                qa_vault.learn(q.strip(), a.strip())
                await self.send_message(f"💾 <b>Saved to Memory!</b>\n\n❓ <b>Question:</b> {html.escape(q.strip())}\n✅ <b>Answer:</b> <code>{html.escape(a.strip())}</code>")
            else:
                await self.send_message("⚠️ <b>Format error.</b> Use: <code>/learn Question = Answer</code>")
            return

        # Case 5: Answering a pending question
        # If user typed /ans <text> or directly sent the answer
        ans_text = text
        if text.lower().startswith("/ans "):
            ans_text = text[5:].strip()

        pending_items = [p for p in qa_vault.get_pending_questions() if p.get("status") == "pending"]
        if not pending_items:
            # If no items currently marked pending, look at the most recent question registered in the vault
            all_questions = qa_vault.get_pending_questions()
            if all_questions:
                pending_items = [all_questions[-1]]

        if pending_items:
            latest_pending = pending_items[-1]
            q_text = latest_pending["question"]
            job_title = latest_pending.get("job_title", "Job")
            company = latest_pending.get("company", "Company")

            # Persist to memory vault
            qa_vault.learn(q_text, ans_text, category="recruiter_qa")

            confirmation = (
                f"💾 <b>Saved & Remembered Forever!</b>\n\n"
                f"❓ <b>Question:</b> {html.escape(q_text)}\n"
                f"✅ <b>Your Answer:</b> <code>{html.escape(ans_text)}</code>\n"
                f"🏢 <b>Company:</b> {html.escape(company)} ({html.escape(job_title)})\n\n"
                f"🎉 I have permanently saved this answer. All future applications will answer this automatically!"
            )
            await self.send_message(confirmation)
            print(f"[Telegram Listener] Successfully processed answer for '{q_text}': '{ans_text}'")
        else:
            # No pending question at all; acknowledge friendly
            await self.send_message(
                f"ℹ️ Received: \"<code>{html.escape(ans_text)}</code>\".\n\n"
                "No recruiter questions are currently waiting for an answer.\n"
                "• View memory: <code>/memory</code>\n"
                "• Teach new answer: <code>/learn Question = Answer</code>"
            )

telegram_listener = TelegramBotListener()
