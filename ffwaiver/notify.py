"""Optional notifications. Off unless enabled in config.json AND the secret is set.

Discord: set the repository secret DISCORD_WEBHOOK_URL.
Email:   set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD secrets and notifications.email.to.
"""
import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage


def _message(data, reasons):
    lines = [f"**{data['badge']['text']}** (week {data['week']})"]
    if data.get("alert"):
        lines.append("🚨 " + data["alert"]["text"])
    for r in reasons[:4]:
        lines.append("• " + r)
    lines.append("Top pickups:")
    for p in [p for p in data["picks"] if p.get("rank")][:3]:
        lines.append(f"{p['rank']}. {p['name']} ({p['pos']}, {p['team']}): {p['reason']}")
    if data.get("site_url"):
        lines.append(data["site_url"])
    return "\n".join(lines)


def send(config, data, reasons):
    n = config.get("notifications") or {}
    if not n.get("enabled"):
        return "notifications disabled"
    text = _message(data, reasons)
    sent = []
    hook = os.environ.get(n.get("discord_webhook_env", "DISCORD_WEBHOOK_URL"))
    if hook:
        try:
            req = urllib.request.Request(hook, data=json.dumps({"content": text[:1900]}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "ff-waiver-site"})
            urllib.request.urlopen(req, timeout=20)
            sent.append("discord")
        except Exception as e:  # never fail the run over a notification
            print(f"::warning::Discord notification failed: {e}")
    em = n.get("email") or {}
    if em.get("enabled") and em.get("to") and os.environ.get(em.get("smtp_host_env", "SMTP_HOST")):
        try:
            msg = EmailMessage()
            msg["Subject"] = f"Waiver wire: {data['badge']['text']}"
            msg["From"] = os.environ.get(em.get("smtp_user_env", "SMTP_USER"), "ff-waiver-site")
            msg["To"] = em["to"]
            msg.set_content(text.replace("**", ""))
            port = int(os.environ.get(em.get("smtp_port_env", "SMTP_PORT"), "587"))
            with smtplib.SMTP(os.environ[em.get("smtp_host_env", "SMTP_HOST")], port, timeout=30) as s:
                s.starttls()
                user = os.environ.get(em.get("smtp_user_env", "SMTP_USER"))
                if user:
                    s.login(user, os.environ.get(em.get("smtp_password_env", "SMTP_PASSWORD"), ""))
                s.send_message(msg)
            sent.append("email")
        except Exception as e:
            print(f"::warning::Email notification failed: {e}")
    return ", ".join(sent) or "no notification channel configured"
