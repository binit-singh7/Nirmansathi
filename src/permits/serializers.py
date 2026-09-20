from rest_framework import serializers
from .models import (
    PermitApplication,
    ApplicationDocument,
    PermitDecision,
    ConstructionPhase,
    ConstructionPhaseDocument
)
from accounts.serializers import CustomUserSerializer

class ApplicationDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.ReadOnlyField(source='get_document_type_display')

    class Meta:
        model = ApplicationDocument
        fields = ['id', 'application', 'document_type', 'document_type_display', 'title', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class PermitDecisionSerializer(serializers.ModelSerializer):
    officer_name = serializers.ReadOnlyField(source='officer.username')
    decision_display = serializers.ReadOnlyField(source='get_decision_display')

    class Meta:
        model = PermitDecision
        fields = ['id', 'application', 'officer', 'officer_name', 'decision', 'decision_display', 'remarks', 'decision_date']
        read_only_fields = ['id', 'officer', 'decision_date']


class ConstructionPhaseDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.ReadOnlyField(source='get_document_type_display')

    class Meta:
        model = ConstructionPhaseDocument
        fields = ['id', 'phase', 'document_type', 'document_type_display', 'title', 'file', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class ConstructionPhaseSerializer(serializers.ModelSerializer):
    status_display = serializers.ReadOnlyField(source='get_status_display')
    reviewed_by_name = serializers.ReadOnlyField(source='reviewed_by.username')
    documents = ConstructionPhaseDocumentSerializer(many=True, read_only=True)
    is_prerequisite_satisfied = serializers.ReadOnlyField()

    class Meta:
        model = ConstructionPhase
        fields = [
            'id', 'application', 'phase_type', 'name', 'sequence',
            'status', 'status_display', 'submitted_at',
            'reviewed_by', 'reviewed_by_name', 'approved_at', 'rejected_at',
            'review_notes', 'generated_approval_pdf', 'generated_stamped_blueprint',
            'documents', 'is_prerequisite_satisfied', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'application', 'phase_type', 'name', 'sequence', 'status',
            'submitted_at', 'reviewed_by', 'approved_at', 'rejected_at',
            'generated_approval_pdf', 'generated_stamped_blueprint',
            'created_at', 'updated_at'
        ]


class PermitApplicationSerializer(serializers.ModelSerializer):
    applicant_name = serializers.ReadOnlyField(source='applicant.username')
    municipality_name = serializers.ReadOnlyField(source='municipality.name')
    ward_number = serializers.ReadOnlyField(source='ward.ward_number')
    application_type_display = serializers.ReadOnlyField(source='get_application_type_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    documents = ApplicationDocumentSerializer(many=True, read_only=True)
    decisions = PermitDecisionSerializer(many=True, read_only=True)
    construction_phases = ConstructionPhaseSerializer(many=True, read_only=True)
    completion_reviewed_by_name = serializers.ReadOnlyField(source='completion_reviewed_by.username')
    can_complete_construction = serializers.ReadOnlyField()

    class Meta:
        model = PermitApplication
        fields = [
            'id', 'reference_number', 'applicant', 'applicant_name',
            'application_type', 'application_type_display',
            'municipality', 'municipality_name', 'ward', 'ward_number',
            'tole_address', 'plot_number', 'land_area_sqft',
            'total_built_up_area_sqft', 'storeys_count', 'estimated_cost',
            'status', 'status_display', 'remarks',
            'permit_approval_letter_pdf',
            'completion_certificate_pdf', 'completed_at',
            'completion_reviewed_by', 'completion_reviewed_by_name',
            'completion_remarks', 'can_complete_construction',
            'documents', 'decisions', 'construction_phases',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reference_number', 'applicant', 'status', 'remarks',
            'permit_approval_letter_pdf',
            'completion_certificate_pdf', 'completed_at', 'completion_reviewed_by',
            'created_at', 'updated_at'
        ]
