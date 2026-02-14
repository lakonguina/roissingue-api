"""
Email delivery service.

This module defines a simple helper function to send plain text
emails via SMTP.  It reads SMTP configuration from the global
``Settings`` object and uses Python's built‑in ``smtplib`` to send
messages.  The service is used by the authentication workflows to
deliver account verification and password reset links.

If the SMTP host is not configured the ``send_email`` function will
raise a ``RuntimeError``.  In a production deployment you should
configure the SMTP host, port and credentials via environment
variables.
"""

import smtplib
import ssl
from email.message import EmailMessage

from settings import settings


def send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_port:
        raise RuntimeError(
            "SMTP configuration is not defined. Set SMTP_HOST and SMTP_PORT in the environment."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
    msg["To"] = to_email
    msg.set_content(body)

    host = settings.smtp_host
    port = int(settings.smtp_port)
    user = settings.smtp_user
    password = settings.smtp_password

    context = ssl.create_default_context()

    try:
        # 465 = implicit SSL
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
                server.ehlo()
                if user and password:
                    server.login(user, password)
                refused = server.send_message(msg)
        else:
            # 587 (ou autre) = STARTTLS (si supporté)
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                # Si ton serveur est en 587, c'est quasi obligatoire
                server.starttls(context=context)
                server.ehlo()
                if user and password:
                    server.login(user, password)
                refused = server.send_message(msg)

        if refused:
            raise RuntimeError(f"Email refused for: {refused}")

    except smtplib.SMTPAuthenticationError as e:
        raise RuntimeError(
            "SMTP auth failed (bad user/password or auth method)."
        ) from e
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP error: {e}") from e
