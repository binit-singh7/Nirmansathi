from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserProfile, AuditLog

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'role', 'phone_number', 'municipality', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('NirmanSathi Details', {'fields': ('role', 'phone_number', 'municipality')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('NirmanSathi Details', {'fields': ('role', 'email', 'phone_number', 'municipality')}),
    )
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('username',)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'company_name', 'created_at')
    search_fields = ('user__username', 'full_name', 'company_name', 'citizenship_number')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'category', 'actor_username', 'action', 'ip_address', 'status')
    list_filter = ('category', 'status', 'timestamp')
    search_fields = ('actor_username', 'action', 'ip_address')
    readonly_fields = ('timestamp', 'category', 'actor', 'actor_username', 'action', 'ip_address', 'status', 'metadata')

