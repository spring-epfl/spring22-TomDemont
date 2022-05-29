from flask_mail import Message

from app import app, celery, mail


@celery.task
def send_mail(subject, recipients, text_body, sender=None, attachments=None) -> None:
    with app.app_context():
        msg = Message(subject, sender=sender, recipients=recipients)
        msg.body = text_body + "\nKind regards,\nSecret Race Strolling Team"
        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)
        mail.send(msg)
