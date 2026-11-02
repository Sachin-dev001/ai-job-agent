import asyncio
from typing import Optional
import httpx
import aiosmtplib
from email.message import EmailMessage
from app.config import settings

class NotificationManager:
    """
    Handles Human-in-the-Loop alerting via Telegram Bot & Email (Gmail SMTP).
    Telegram provides 100% free, unlimited, real-time alerts with clickable markdown links.
    """
    def __init__(self):
        self.telegram_enabled = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)
        self.email_enabled = bool(settings.SMTP_USER and settings.SMTP_PASS and settings.USER_EMAIL)

    async def send_hitl_alert(self, job_title: str, company: str, platform: str, job_url: str, reason: str, question: Optional[str] = None):
        """Dispatches alert across enabled channels."""
        tasks = []
        if self.telegram_enabled:
            tasks.append(self._send_telegram(job_title, company, platform, job_url, reason, question))
        if self.email_enabled:
            tasks.append(self._send_email(job_title, company, platform, job_url, reason, question))

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

    async def _send_telegram(self, job_title: str, company: str, platform: str, job_url: str, reason: str, question: Optional[str] = None):
        """Sends rich formatted message to your Telegram account/chat."""
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

    async def _send_email(self, job_title: str, company: str, platform: str, job_url: str, reason: str, question: Optional[str] = None):
        try:
            msg = EmailMessage()
            msg["From"] = settings.SMTP_USER
            msg["To"] = settings.USER_EMAIL
            msg["Subject"] = f"⚠️ Action Required: {job_title} at {company} ({platform})"

            content = f"""
            Hello,

            Your AI Job Agent paused on an application that requires your intervention:

            Role: {job_title}
            Company: {company}
            Platform: {platform}
            Reason: {reason}
            """
            if question:
                content += f"\nScreening Question: {question}\n"

            content += f"""
            Link to complete or resolve:
            {job_url}

            Best regards,
            AI Job Agent
            """
            msg.set_content(content)

            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASS,
                start_tls=True
            )
        except Exception as e:
            print(f"[Email Alert Failed]: {e}")

notifier = NotificationManager()
