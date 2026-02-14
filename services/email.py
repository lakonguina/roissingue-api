from typing import Optional

from settings import settings


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send a plain text email.

    :param to_email: recipient email address
    :param subject: subject line for the email
    :param body: plain text body of the message
    :raises RuntimeError: if SMTP configuration is incomplete
    """
    # Ensure SMTP is configured
    if not settings.smtp_host or not settings.smtp_port:
        raise RuntimeError(
            "SMTP configuration is not defined. Set SMTP_HOST and SMTP_PORT in the environment."
        )
    # Construct the message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
    msg["To"] = to_email
    msg.set_content(body)

    # Open an SMTP connection and send the message
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        # Upgrade the connection to TLS if requested
        if settings.smtp_use_tls:
            server.starttls()
        # Authenticate if credentials are provided
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        # Send the message
        server.send_message(msg)
