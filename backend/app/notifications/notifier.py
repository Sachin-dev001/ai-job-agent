import os
import smtplib
import asyncio
from email.message import EmailMessage
from typing import Optional
import httpx
from app.config import settings

class NotificationService:
    """Multi-channel Human-In-The-Loop alerting service (Telegram & Email)."""

    def __init__(self):
        self.telegram_enabled = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
        self.email_enabled = bool(settings.SMTP_USER and settings.SMTP_PASS and settings.USER_EMAIL)

    async def send_hitl_alert(self, job_title: str, company: str, platform: str, job_url: str, reason: str, question: Optional[str] = None, user_id: Optional[str] = None, question_id: Optional[str] = None):
        """Dispatches alert across enabled channels with tenant metadata tags."""
        tasks = []
        if self.telegram_enabled:
            tasks.append(self._send_telegram(job_title, company, platform, job_url, reason, question, user_id=user_id, question_id=question_id))
        if self.email_enabled:
            tasks.append(self._send_email(job_title, company, platform, job_url, reason, question, user_id=user_id, question_id=question_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        else:
            print(f"[HITL Alert - Local Fallback] Job: {job_title} @ {company} ({platform}) | Reason: {reason} | Link: {job_url}")

    async def send_cover_letter_alert(self, job_title: str, company: str, platform: str, job_url: str, cover_letter: str):
        """Notifies user via Telegram that an application pitch was generated."""
        if not self.telegram_enabled:
            return
        try:
            bot_token = settings.TELEGRAM_BOT_TOKEN
            chat_id = settings.TELEGRAM_CHAT_ID

            preview = cover_letter[:350] + ("..." if len(cover_letter) > 350 else "")
            text = (
                f"📝 *Tailored Application Package Ready*\n\n"
                f"💼 *Role:* {job_title}\n"
                f"🏢 *Company:* {company}\n"
                f"🌐 *Platform:* {platform}\n\n"
                f"📄 *Pitch Preview:*\n_{preview}_\n\n"
                f"🔗 [Click to View Job Listing]({job_url})"
            )

            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(api_url, json=payload)
        except Exception as e:
            print(f"[Telegram Pitch Notification Note]: {e}")

    async def _send_telegram(self, job_title: str, company: str, platform: str, job_url: str, reason: str, question: Optional[str] = None, user_id: Optional[str] = None, question_id: Optional[str] = None):
        """Sends rich formatted message to Telegram account with multi-tenant tag."""
        try:
            bot_token = settings.TELEGRAM_BOT_TOKEN
            chat_id = settings.TELEGRAM_CHAT_ID

            text = (
                f"🚨 *AI Job Agent — Human Action Needed*\n\n"
                f"💼 *Role:* {job_title}\n"
                f"🏢 *Company:* {company}\n"
                f"🌐 *Platform:* {platform}\n"
                f"⚠️ *Issue:* {reason}\n"
            )
            if question:
                text += f"\n❓ *Question Asked:* _{question}_\n"

            text += f"\n🔗 [Click Here to View / Apply Job]({job_url})"

            if question_id or user_id:
                qid = question_id or "q"
                uid = user_id or "guest-candidate"
                text += f"\n\n`[QID:{qid} | UID:{uid}]`"

            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(api_url, json=payload)
                if res.status_code != 200:
                    print(f"[Telegram Alert Error] status: {res.status_code}, response: {res.text}")
        except Exception as e:
            print(f"[Telegram Alert Failed]: {e}")

    async def _send_email(self, job_title: str, company: str, platform: str, job_url: str, reason: str, question: Optional[str] = None, user_id: Optional[str] = None, question_id: Optional[str] = None):
        try:
            msg = EmailMessage()
            msg["From"] = settings.SMTP_USER
            msg["To"] = settings.USER_EMAIL
            msg["Subject"] = f"⚠️ Action Required: {job_title} at {company} ({platform})"

            body = (
                f"Hello,\n\n"
                f"Your autonomous AI Job Application Agent encountered a step requiring your action.\n\n"
                f"Job: {job_title}\n"
                f"Company: {company}\n"
                f"Platform: {platform}\n"
                f"Reason: {reason}\n"
            )
            if question:
                body += f"Recruiter Question: {question}\n"

            if question_id or user_id:
                body += f"Tag: [QID:{question_id or 'q'} | UID:{user_id or 'guest-candidate'}]\n"

            body += f"\nDirect Link: {job_url}\n\nBest,\nYour Autonomous Job Agent"
            msg.set_content(body)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_smtp_sync, msg)
        except Exception as e:
            print(f"[Email Notification Error]: {e}")

    def _send_smtp_sync(self, msg: EmailMessage):
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)

notifier = NotificationService()
