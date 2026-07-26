from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction

from .models import PermitApplication, ApplicationDocument, PermitDecision
from .serializers import (
    PermitApplicationSerializer,
    ApplicationDocumentSerializer,
    PermitDecisionSerializer
)
from .permissions import IsPermitParticipant

class PermitApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = PermitApplicationSerializer
    permission_classes = [IsPermitParticipant]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference_number', 'tole_address', 'plot_number']
    ordering_fields = ['created_at', 'updated_at', 'status']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return PermitApplication.objects.none()

        if user.is_staff or user.role == 'ADMIN':
            return PermitApplication.objects.all()

        if user.is_citizen:
            return PermitApplication.objects.filter(applicant=user)

        if user.is_municipality_officer:
            if user.municipality:
                return PermitApplication.objects.filter(municipality=user.municipality)
            return PermitApplication.objects.all()

        return PermitApplication.objects.none()

    def perform_create(self, serializer):
        serializer.save(applicant=self.request.user, status=PermitApplication.Status.PENDING)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def review(self, request, pk=None):
        """
        Officer Review & Decision Endpoint (FR-06)
        """
        application = self.get_object()
        user = request.user

        if not (user.is_municipality_officer or user.is_staff or user.role == 'ADMIN'):
            return Response(
                {"error": "Only municipality officers can review building permit applications."},
                status=status.HTTP_403_FORBIDDEN
            )

        decision_choice = request.data.get('decision')
        remarks = request.data.get('remarks', '')

        if decision_choice not in [PermitDecision.DecisionChoice.APPROVED, PermitDecision.DecisionChoice.REJECTED, PermitDecision.DecisionChoice.UNDER_REVIEW]:
            return Response(
                {"error": "Invalid decision. Choose APPROVED, REJECTED, or UNDER_REVIEW."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            decision = PermitDecision.objects.create(
                application=application,
                officer=user,
                decision=decision_choice,
                remarks=remarks
            )
            # Update application status
            if decision_choice == PermitDecision.DecisionChoice.APPROVED:
                application.status = PermitApplication.Status.APPROVED
            elif decision_choice == PermitDecision.DecisionChoice.REJECTED:
                application.status = PermitApplication.Status.REJECTED
            else:
                application.status = PermitApplication.Status.UNDER_REVIEW

            application.remarks = remarks
            application.save()

        return Response({
            'message': f'Application status updated to {application.get_status_display()}.',
            'application': PermitApplicationSerializer(application).data,
            'decision': PermitDecisionSerializer(decision).data
        }, status=status.HTTP_200_OK)


class ApplicationDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == 'ADMIN':
            return ApplicationDocument.objects.all()
        return ApplicationDocument.objects.filter(application__applicant=user)
