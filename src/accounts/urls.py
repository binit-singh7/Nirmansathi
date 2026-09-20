from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterView, CurrentUserView, UserProfileView,
    UpdateCurrentUserView, ChangePasswordView,
    AdminUserListView, AdminUserRoleUpdateView, AuditLogListView,
    AdminOfficerVerificationView
)
from .ocr_views import NIDVerifyView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', CurrentUserView.as_view(), name='auth_me'),
    path('me/update/', UpdateCurrentUserView.as_view(), name='auth_me_update'),
    path('me/change-password/', ChangePasswordView.as_view(), name='auth_change_password'),
    path('profile/', UserProfileView.as_view(), name='auth_profile'),

    # NID / Citizenship document OCR verification (backend-only, authenticated)
    path('nid/verify/', NIDVerifyView.as_view(), name='nid_verify'),

    # Admin-only user management
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('users/<int:pk>/role/', AdminUserRoleUpdateView.as_view(), name='admin_user_role_update'),
    path('officers/<int:pk>/verify/', AdminOfficerVerificationView.as_view(), name='admin_officer_verify'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit_logs_list'),
]
