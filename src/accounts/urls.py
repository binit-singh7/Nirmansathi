from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterView, CurrentUserView, UserProfileView,
    AdminUserListView, AdminUserRoleUpdateView, AuditLogListView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserView.as_view(), name='auth_me'),
    path('profile/', UserProfileView.as_view(), name='auth_profile'),

    # Admin-only user management
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('users/<int:pk>/role/', AdminUserRoleUpdateView.as_view(), name='admin_user_role_update'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit_logs_list'),
]

