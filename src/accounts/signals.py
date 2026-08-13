from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from .models import AuditLog
from .utils import log_audit

@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR', '127.0.0.1') if request else '127.0.0.1'
    log_audit(
        category=AuditLog.Category.AUTH,
        action=f"User '{user.username}' logged in successfully (JWT / Session).",
        user=user,
        ip_address=ip,
        status=AuditLog.Status.SUCCESS
    )

@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    ip = request.META.get('REMOTE_ADDR', '127.0.0.1') if request else '127.0.0.1'
    username = credentials.get('username') or credentials.get('email') or 'unknown'
    log_audit(
        category=AuditLog.Category.AUTH,
        action=f"Failed login attempt for username/email '{username}'.",
        username=username,
        ip_address=ip,
        status=AuditLog.Status.FAILED
    )
