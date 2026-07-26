from rest_framework import serializers
from .models import PermitApplication, ApplicationDocument, PermitDecision
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


class PermitApplicationSerializer(serializers.ModelSerializer):
    applicant_name = serializers.ReadOnlyField(source='applicant.username')
    municipality_name = serializers.ReadOnlyField(source='municipality.name')
    ward_number = serializers.ReadOnlyField(source='ward.ward_number')
    application_type_display = serializers.ReadOnlyField(source='get_application_type_display')
    status_display = serializers.ReadOnlyField(source='get_status_display')
    documents = ApplicationDocumentSerializer(many=True, read_only=True)
    decisions = PermitDecisionSerializer(many=True, read_only=True)

    class Meta:
        model = PermitApplication
        fields = [
            'id', 'reference_number', 'applicant', 'applicant_name',
            'application_type', 'application_type_display',
            'municipality', 'municipality_name', 'ward', 'ward_number',
            'tole_address', 'plot_number', 'land_area_sqft',
            'total_built_up_area_sqft', 'storeys_count', 'estimated_cost',
            'status', 'status_display', 'remarks',
            'documents', 'decisions', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reference_number', 'applicant', 'status', 'remarks',
            'created_at', 'updated_at'
        ]
