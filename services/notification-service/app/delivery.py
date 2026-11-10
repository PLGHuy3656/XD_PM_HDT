import json
import logging
import smtplib
from email.message import EmailMessage

from app import repositories
from app.config import settings

logger = logging.getLogger(__name__)


def send_email(notification: dict, recipient: tuple[str, str]) -> bool:
    if not settings.smtp_host or not settings.smtp_sender:
        logger.warning("Email notification skipped: SMTP is not configured")
        return False

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
    return True


def send_web_push(notification: dict, user_id: str) -> bool:
    if not (
        settings.vapid_private_key
        and settings.vapid_subject
    ):
        logger.warning("Web push skipped: VAPID is not configured")
        return False

    from pywebpush import WebPushException, webpush

    subscriptions = repositories.get_push_subscriptions(user_id)
    if not subscriptions:
        return False
    delivery_errors = []
    delivered_count = 0
    for subscription in subscriptions:
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(notification),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
            )
            delivered_count += 1
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
            else:
                delivery_errors.append(status_code or "unknown")
    if delivery_errors:
        raise RuntimeError(
            f"Web Push failed for {len(delivery_errors)} subscription(s)"
        )
    return delivered_count > 0


def send_fcm(notification: dict, user_id: str) -> bool:
    if not settings.firebase_service_account_path:
        logger.warning("FCM delivery skipped: Firebase credentials are not configured")
        return False

    import firebase_admin
    from firebase_admin import credentials, messaging

    tokens = repositories.get_fcm_tokens(user_id)
    if not tokens:
        return False

    try:
        firebase_app = firebase_admin.get_app("notification-service")
    except ValueError:
        credential = credentials.Certificate(settings.firebase_service_account_path)
        options = (
            {"projectId": settings.firebase_project_id}
            if settings.firebase_project_id
            else None
        )
        firebase_app = firebase_admin.initialize_app(
            credential,
            options=options,
            name="notification-service",
        )

    delivery_errors = []
    delivered_count = 0
    for token in tokens:
        try:
            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(
                        title=notification["title"],
                        body=notification["message"],
                    ),
                    data={
                        "notification_id": str(notification["id"]),
                        "event_type": str(notification["event_type"]),
                    },
                    token=token,
                ),
                app=firebase_app,
            )
            delivered_count += 1
        except messaging.UnregisteredError:
            logger.info("Removing expired FCM token")
            repositories.delete_fcm_token(user_id, token)
        except Exception:
            logger.exception(
                "FCM delivery failed for notification %s",
                notification["id"],
            )
            delivery_errors.append(token)
    if delivery_errors:
        raise RuntimeError(
            f"FCM failed for {len(delivery_errors)} registration token(s)"
        )
    return delivered_count > 0
