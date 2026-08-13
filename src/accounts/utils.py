from .models import AuditLog

def log_audit(category, action, user=None, username=None, ip_address=None, status=AuditLog.Status.SUCCESS, metadata=None):
    actor_name = username
    if user and hasattr(user, 'username') and user.username:
        actor_name = user.username
    if not actor_name:
        actor_name = 'unauthenticated_client'

    actor_obj = user if (user and hasattr(user, 'is_authenticated') and user.is_authenticated) else None

    return AuditLog.objects.create(
        category=category,
        action=action,
        actor=actor_obj,
        actor_username=actor_name,
        ip_address=ip_address or '127.0.0.1',
        status=status,
        metadata=metadata
    )
