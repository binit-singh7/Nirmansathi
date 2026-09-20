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
        CONSTRUCTION_ONGOING = 'CONSTRUCTION_ONGOING', _('Construction Ongoing')
        COMPLETION_PENDING = 'COMPLETION_PENDING', _('Completion Pending')
        COMPLETED = 'COMPLETED', _('Completed')
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

    # Permit Approval Letter (generated when officer approves the initial permit)
    permit_approval_letter_pdf = models.FileField(
        upload_to='generated_documents/permit_approval_letters/%Y/%m/',
        null=True,
        blank=True
    )

    # Final Construction Completion Fields
    completion_certificate_pdf = models.FileField(
        upload_to='generated_documents/completion_certificates/%Y/%m/',
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='completed_permits'
    )
    completion_remarks = models.TextField(blank=True, null=True, help_text=_("Final inspection notes or completion remarks"))

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

    def initialize_construction_phases(self, force=False):
        """
        Initializes the sequential construction phases based on storeys_count.
        Ensures PLINTH, floor-specific phases, and FINAL COMPLETION exist matching storeys_count.
        """
        target_storeys = max(1, self.storeys_count or 1)
        target_phase_count = target_storeys + 2  # 1 plinth + N floors + 1 completion
        existing_phases = list(self.construction_phases.all())

        if existing_phases and not force:
            # If any phase has progressed beyond PENDING, preserve history
            has_activity = any(p.status != ConstructionPhase.PhaseStatus.PENDING for p in existing_phases)
            if has_activity or len(existing_phases) == target_phase_count:
                return existing_phases
            # If all phases are still PENDING and count does not match storeys_count, clear to resync
            self.construction_phases.all().delete()

        floor_names = [
            (1, 'FIRST_FLOOR', _('First Floor')),
            (2, 'SECOND_FLOOR', _('Second Floor')),
            (3, 'THIRD_FLOOR', _('Third Floor')),
            (4, 'FOURTH_FLOOR', _('Fourth Floor')),
            (5, 'FIFTH_FLOOR', _('Fifth Floor')),
            (6, 'SIXTH_FLOOR', _('Sixth Floor')),
            (7, 'SEVENTH_FLOOR', _('Seventh Floor')),
            (8, 'EIGHTH_FLOOR', _('Eighth Floor')),
            (9, 'NINTH_FLOOR', _('Ninth Floor')),
            (10, 'TENTH_FLOOR', _('Tenth Floor')),
        ]

        phases_to_create = []
        seq = 1
        # 1. Plinth Phase
        phases_to_create.append(ConstructionPhase(
            application=self,
            phase_type=ConstructionPhase.PhaseType.PLINTH,
            name='Plinth Level',
            sequence=seq,
            status=ConstructionPhase.PhaseStatus.PENDING
        ))
        seq += 1

        # 2. Storey Phases strictly according to submitted storeys_count
        for i in range(1, target_storeys + 1):
            if i <= len(floor_names):
                p_type = floor_names[i - 1][1]
                p_label = str(floor_names[i - 1][2])
            else:
                p_type = f"FLOOR_{i}"
                p_label = f"Floor {i}"
            phases_to_create.append(ConstructionPhase(
                application=self,
                phase_type=p_type,
                name=p_label,
                sequence=seq,
                status=ConstructionPhase.PhaseStatus.PENDING
            ))
            seq += 1

        # 3. Final Completion Phase
        phases_to_create.append(ConstructionPhase(
            application=self,
            phase_type=ConstructionPhase.PhaseType.FINAL_COMPLETION,
            name='Final Completion Inspection',
            sequence=seq,
            status=ConstructionPhase.PhaseStatus.PENDING
        ))

        ConstructionPhase.objects.bulk_create(phases_to_create)
        return list(self.construction_phases.all())

    @property
    def can_complete_construction(self):
        """Checks if all prerequisite floor/plinth phases are approved before completion"""
        floor_phases = self.construction_phases.exclude(
            phase_type=ConstructionPhase.PhaseType.FINAL_COMPLETION
        )
        if not floor_phases.exists():
            return False
        return not floor_phases.exclude(status=ConstructionPhase.PhaseStatus.APPROVED).exists()

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


class ConstructionPhase(models.Model):
    class PhaseType(models.TextChoices):
        PLINTH = 'PLINTH', _('Plinth Level')
        FIRST_FLOOR = 'FIRST_FLOOR', _('First Floor')
        SECOND_FLOOR = 'SECOND_FLOOR', _('Second Floor')
        THIRD_FLOOR = 'THIRD_FLOOR', _('Third Floor')
        FOURTH_FLOOR = 'FOURTH_FLOOR', _('Fourth Floor')
        FIFTH_FLOOR = 'FIFTH_FLOOR', _('Fifth Floor')
        SIXTH_FLOOR = 'SIXTH_FLOOR', _('Sixth Floor')
        SEVENTH_FLOOR = 'SEVENTH_FLOOR', _('Seventh Floor')
        EIGHTH_FLOOR = 'EIGHTH_FLOOR', _('Eighth Floor')
        NINTH_FLOOR = 'NINTH_FLOOR', _('Ninth Floor')
        TENTH_FLOOR = 'TENTH_FLOOR', _('Tenth Floor')
        ADDITIONAL_FLOOR = 'ADDITIONAL_FLOOR', _('Additional Floor')
        FINAL_COMPLETION = 'FINAL_COMPLETION', _('Final Completion')

    class PhaseStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending Submission')
        SUBMITTED = 'SUBMITTED', _('Submitted for Review')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')

    application = models.ForeignKey(
        PermitApplication,
        on_delete=models.CASCADE,
        related_name='construction_phases'
    )
    phase_type = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    sequence = models.PositiveIntegerField()
    status = models.CharField(
        max_length=30,
        choices=PhaseStatus.choices,
        default=PhaseStatus.PENDING
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_construction_phases'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, null=True, help_text=_("Officer inspection remarks"))
    generated_approval_pdf = models.FileField(
        upload_to='generated_documents/phase_approvals/%Y/%m/',
        null=True,
        blank=True
    )
    generated_stamped_blueprint = models.FileField(
        upload_to='generated_documents/stamped_blueprints/%Y/%m/',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sequence']
        unique_together = ('application', 'sequence')

    def __str__(self):
        return f"{self.application.reference_number} - Phase {self.sequence}: {self.name} ({self.get_status_display()})"

    @property
    def is_prerequisite_satisfied(self):
        """Check if preceding phase (sequence - 1) is approved"""
        if self.sequence <= 1:
            return self.application.status in [
                PermitApplication.Status.APPROVED,
                PermitApplication.Status.CONSTRUCTION_ONGOING,
                PermitApplication.Status.COMPLETION_PENDING,
                PermitApplication.Status.COMPLETED
            ]
        prev_phase = self.application.construction_phases.filter(sequence=self.sequence - 1).first()
        return bool(prev_phase and prev_phase.status == self.PhaseStatus.APPROVED)

    @property
    def blueprint_document(self):
        """Returns the primary blueprint document for this phase if available"""
        return self.documents.filter(document_type=ConstructionPhaseDocument.DocumentType.BLUEPRINT).first()


class ConstructionPhaseDocument(models.Model):
    class DocumentType(models.TextChoices):
        BLUEPRINT = 'BLUEPRINT', _('Architectural / Structural Blueprint')
        SITE_PHOTO = 'SITE_PHOTO', _('Site Construction Photo')
        INSPECTION_REPORT = 'INSPECTION_REPORT', _('Field Inspection Report')
        COMPLETION_REPORT = 'COMPLETION_REPORT', _('Phase Completion Report')
        OTHER = 'OTHER', _('Other Supporting Document')

    phase = models.ForeignKey(
        ConstructionPhase,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices,
        default=DocumentType.BLUEPRINT
    )
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='construction_phases/original/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.phase.name} ({self.phase.application.reference_number})"


