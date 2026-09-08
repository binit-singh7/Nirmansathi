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
from accounts.utils import log_audit
from accounts.models import AuditLog

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
            if user.is_verified_officer and user.municipality:
                return PermitApplication.objects.filter(municipality=user.municipality)
            return PermitApplication.objects.none()

        return PermitApplication.objects.none()

    def perform_create(self, serializer):
        app = serializer.save(applicant=self.request.user, status=PermitApplication.Status.PENDING)
        ip = self.request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.PERMIT,
            action=f"Submitted new building permit application '{app.reference_number}'.",
            user=self.request.user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def review(self, request, pk=None):
        """
        Officer Review & Decision Endpoint (FR-06)
        """
        user = request.user

        if user.is_municipality_officer:
            if not user.is_verified_officer:
                return Response(
                    {"error": "Your officer account is pending verification or rejected. You cannot review applications."},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif not (user.is_staff or user.role == 'ADMIN'):
            return Response(
                {"error": "Only municipality officers or administrators can review building permit applications."},
                status=status.HTTP_403_FORBIDDEN
            )

        application = self.get_object()

        if user.is_municipality_officer:
            if not user.municipality or application.municipality != user.municipality:
                return Response(
                    {"error": "You do not have jurisdiction over this application's municipality."},
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
            elif decision_choice == PermitDecision.DecisionChoice.UNDER_REVIEW:
                application.status = PermitApplication.Status.UNDER_REVIEW
            application.save(update_fields=['status'])

            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            log_audit(
                category=AuditLog.Category.PERMIT,
                action=f"Decision '{decision_choice}' recorded for permit application '{application.reference_number}'.",
                user=user,
                ip_address=ip,
                status=AuditLog.Status.SUCCESS
            )

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
        if not user.is_authenticated:
            return ApplicationDocument.objects.none()

        if user.is_staff or user.role == 'ADMIN':
            return ApplicationDocument.objects.all()

        if user.is_citizen:
            return ApplicationDocument.objects.filter(application__applicant=user)

        if user.is_municipality_officer:
            if user.is_verified_officer and user.municipality:
                return ApplicationDocument.objects.filter(application__municipality=user.municipality)
            return ApplicationDocument.objects.none()

        return ApplicationDocument.objects.none()
