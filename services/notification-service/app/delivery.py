import json
import logging
import smtplib
from email.message import EmailMessage

from app import repositories
from app.config import settings

logger = logging.getLogger(__name__)


def send_email(notification: dict, recipient: tuple[str, str]) -> None:
    if not settings.smtp_host or not settings.smtp_sender:
        logger.warning("Email notification skipped: SMTP is not configured")
        return

    email, full_name = recipient
    message = EmailMessage()
    message["Subject"] = notification["title"]
    message["From"] = settings.smtp_sender
    message["To"] = email
    message.set_content(
        f"Xin chào {full_name},\n\n"
        f"{notification['message']}\n\n"
        "SwiftletCare"
    )

    if settings.smtp_port == 465:
        smtp = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=10,
        )
    else:
        smtp = smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=10,
        )

    with smtp:
        if settings.smtp_starttls and settings.smtp_port != 465:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_web_push(notification: dict, user_id: str) -> None:
    if not (
        settings.vapid_private_key
        and settings.vapid_subject
    ):
        logger.warning("Web push skipped: VAPID is not configured")
        return

    from pywebpush import WebPushException, webpush

    subscriptions = repositories.get_push_subscriptions(user_id)
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(notification),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
        except WebPushException as exc:
            status_code = (
                exc.response.status_code
                if exc.response is not None
                else None
            )
            logger.warning(
                "Web push delivery failed with HTTP %s",
                status_code or "unknown",
            )
            if status_code in {404, 410}:
                repositories.delete_push_subscription(
                    user_id,
                    subscription["endpoint"],
                )
