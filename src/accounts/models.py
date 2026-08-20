from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = 'CITIZEN', _('Citizen')
        MUNICIPALITY_OFFICER = 'MUNICIPALITY_OFFICER', _('Municipality Officer')
        MATERIAL_SUPPLIER = 'MATERIAL_SUPPLIER', _('Material Supplier')
        ADMIN = 'ADMIN', _('System Administrator')

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.CITIZEN,
        help_text=_("User's primary role in NirmanSathi system.")
    )
    email = models.EmailField(unique=True, help_text=_("Unique email address for registration and login."))
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Optional link to municipality for municipality officers and localized citizens
    municipality = models.ForeignKey(
        'locations.Municipality',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='officers_and_citizens',
        help_text=_("Assigned municipality (especially for officers)")
    )

    REQUIRED_FIELDS = ['email', 'role']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_citizen(self):
        return self.role == self.Role.CITIZEN

    @property
    def is_municipality_officer(self):
        return self.role == self.Role.MUNICIPALITY_OFFICER

    @property
    def is_material_supplier(self):
        return self.role == self.Role.MATERIAL_SUPPLIER


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=150, blank=True)
    citizenship_number = models.CharField(max_length=50, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True, help_text=_("For material suppliers"))
    company_pan_vat = models.CharField(max_length=50, blank=True, null=True, help_text=_("PAN/VAT for suppliers"))
    address = models.CharField(max_length=255, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class AuditLog(models.Model):
    class Category(models.TextChoices):
        AUTH = 'AUTH', _('Authentication & JWT')
        PERMIT = 'PERMIT', _('Building Permits & Inspections')
        PAYMENT = 'PAYMENT', _('eSewa Payments')
        MARKETPLACE = 'MARKETPLACE', _('Marketplace & Orders')
        ADMIN = 'ADMIN', _('System Administration')

    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.AUTH)
    actor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    actor_username = models.CharField(max_length=150, blank=True, help_text="Stored username in case user is deleted or unauthenticated")
    action = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUCCESS)
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.category} - {self.actor_username}: {self.action} ({self.status})"

