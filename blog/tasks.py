# blog/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_comment_notification_email(article_title, recipient_email, comment_content):
    """
    异步发送评论通知邮件
    """
    subject = f'您的文章《{article_title}》有新评论'
    message = f'用户发表了评论：\n\n"{comment_content}"'
    email_from = settings.DEFAULT_FROM_EMAIL

    # 使用更详细的配置
    send_mail(
        subject=subject,
        message=message,
        from_email=email_from,
        recipient_list=[recipient_email],
        fail_silently=False,
    )