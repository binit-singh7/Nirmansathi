import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

def generate_reference_number():
    return f"NS-PERMIT-{uuid.uuid4().hex[:8].upper()}"

class PermitApplication(models.Model):
    class ApplicationType(models.TextChoices):
        NEW_CONSTRUCTION = 'NEW_CONSTRUCTION', _('New Residential Building Construction')
        RENOVATION = 'RENOVATION', _('Building Renovation')
        EXTENSION = 'EXTENSION', _('Building Extension / Storey Addition')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending Review')
        UNDER_REVIEW = 'UNDER_REVIEW', _('Under Technical Review')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='permit_applications'
    )
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        default=generate_reference_number,
        editable=False
    )
    application_type = models.CharField(
        max_length=30,
        choices=ApplicationType.choices,
        default=ApplicationType.NEW_CONSTRUCTION
    )
    
    # Location details
    municipality = models.ForeignKey(
        'locations.Municipality',
        on_delete=models.PROTECT,
        related_name='permit_applications'
    )
    ward = models.ForeignKey(
        'locations.Ward',
        on_delete=models.PROTECT,
        related_name='permit_applications'
    )
    tole_address = models.CharField(max_length=255, help_text=_("Tole or Street Address"))
    plot_number = models.CharField(max_length=100, help_text=_("Kitta Number"))
    
    # Building Specifications
    land_area_sqft = models.DecimalField(max_digits=10, decimal_places=2, help_text=_("Land Area in Sq. Ft."))
    total_built_up_area_sqft = models.DecimalField(max_digits=10, decimal_places=2, help_text=_("Proposed Built-up Area in Sq. Ft."))
    storeys_count = models.PositiveIntegerField(default=1, help_text=_("Number of Storeys"))
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, help_text=_("Estimated Construction Cost (NPR)"))
    
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING
    )
    
    remarks = models.TextField(blank=True, null=True, help_text=_("Officer notes or feedback"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if self.estimated_cost <= 0:
            raise ValidationError({'estimated_cost': 'Estimated cost must be greater than zero.'})
        if self.land_area_sqft <= 0:
            raise ValidationError({'land_area_sqft': 'Land area must be greater than zero.'})
        if self.total_built_up_area_sqft <= 0:
            raise ValidationError({'total_built_up_area_sqft': 'Built up area must be greater than zero.'})

    def __str__(self):
        return f"{self.reference_number} - {self.applicant.get_full_name() or self.applicant.username} ({self.get_status_display()})"


class ApplicationDocument(models.Model):
    class DocumentType(models.TextChoices):
        BLUEPRINT = 'BLUEPRINT', _('Architectural / Structural Blueprint')
        CITIZENSHIP = 'CITIZENSHIP', _('Citizenship Certificate Copy')
        LALPURJA = 'LALPURJA', _('Land Ownership Certificate (Lalpurja)')
        TAX_CLEARANCE = 'TAX_CLEARANCE', _('Property Tax Clearance Receipt')
        OTHER = 'OTHER', _('Other Supporting Document')

    application = models.ForeignKey(
        PermitApplication,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        default=DocumentType.BLUEPRINT
    )
    title = models.CharField(max_length=200, help_text=_("Brief descriptive title of the document"))
    file = models.FileField(upload_to='permit_documents/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.application.reference_number}"


class PermitDecision(models.Model):
    class DecisionChoice(models.TextChoices):
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        UNDER_REVIEW = 'UNDER_REVIEW', _('Under Technical Review')

    application = models.ForeignKey(
        PermitApplication,
        on_delete=models.CASCADE,
        related_name='decisions'
    )
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='permit_decisions'
    )
    decision = models.CharField(max_length=30, choices=DecisionChoice.choices)
    remarks = models.TextField(help_text=_("Detailed officer justification / inspection feedback"))
    decision_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-decision_date']

    def __str__(self):
        return f"Decision: {self.get_decision_display()} by {self.officer.username} on {self.application.reference_number}"

