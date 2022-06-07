"""Defines the tasks and jobs triggered for the control aspects of the application."""


from typing import Any

from flask_mail import Message

from app import app, celery, mail


@celery.task
def send_mail(
    subject: str,
    recipients: list[str],
    text_body: str,
    sender: str = None,
    attachments: Any = None,
) -> None:
    """Sends a mail asynchronously with a celery job.

    Args:
        subject: mail subjects
        recipients: list of email of recipients
        text_body: the body content of the sent mail
        sender: defines a sender if this one is different from app.config['MAIL_DEFAULT_SENDER']
        attachments: file to be sent as attachment in mail"""
    with app.app_context():
        # requires to recall app context as celery job is not
        # necessarily aware and we need flask-mail module and context
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body + "\nKind regards,\nSecret Race Strolling Team"
        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)
        mail.send(msg)
