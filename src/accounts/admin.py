from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserProfile

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
