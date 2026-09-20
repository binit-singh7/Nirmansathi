from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    PermitApplication,
    ApplicationDocument,
    PermitDecision,
    ConstructionPhase,
    ConstructionPhaseDocument
)
from .serializers import (
    PermitApplicationSerializer,
    ApplicationDocumentSerializer,
    PermitDecisionSerializer,
    ConstructionPhaseSerializer,
    ConstructionPhaseDocumentSerializer
)
from .permissions import IsPermitParticipant
from .pdf_services import (
    generate_permit_approval_letter_pdf,
    generate_phase_approval_pdf,
    generate_completion_certificate_pdf,
    stamp_phase_blueprint
)
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

        # The officer review payload includes nested construction phases and their
        # citizen-uploaded documents.  Load that relationship as part of the
        # application query so it is consistently present when the nested
        # serializers render the review response.
        review_queryset = PermitApplication.objects.prefetch_related(
            'documents',
            'decisions',
            'construction_phases__documents',
        )

        if user.is_staff or user.role == 'ADMIN':
            return review_queryset

        if user.is_citizen:
            return review_queryset.filter(applicant=user)

        if user.is_municipality_officer:
            if user.is_verified_officer and user.municipality:
                return review_queryset.filter(municipality=user.municipality)
            return PermitApplication.objects.none()

        return PermitApplication.objects.none()

    def perform_create(self, serializer):
        app = serializer.save(applicant=self.request.user, status=PermitApplication.Status.PENDING)
        # Immediately initialize construction phases according to submitted storeys_count from application form
        app.initialize_construction_phases()
        ip = self.request.META.get('REMOTE_ADDR', '127.0.0.1')
        log_audit(
            category=AuditLog.Category.PERMIT,
            action=f"Submitted new building permit application '{app.reference_number}' with {app.storeys_count} storeys.",
            user=self.request.user,
            ip_address=ip,
            status=AuditLog.Status.SUCCESS
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Ensure construction phases match submitted storeys_count
        instance.initialize_construction_phases()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

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
                application.initialize_construction_phases()
                # Generate permit approval letter PDF
                try:
                    generate_permit_approval_letter_pdf(application, decision)
                except Exception:
                    pass  # Non-blocking: PDF generation failure must not block approval
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

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def start_construction(self, request, pk=None):
        """
        Transitions approved permit to CONSTRUCTION_ONGOING and ensures phases are initialized.
        """
        app = self.get_object()
        if app.status not in [PermitApplication.Status.APPROVED, PermitApplication.Status.CONSTRUCTION_ONGOING]:
            return Response(
                {"error": "Permit must be in APPROVED status to transition to CONSTRUCTION ONGOING."},
                status=status.HTTP_400_BAD_REQUEST
            )

        app.status = PermitApplication.Status.CONSTRUCTION_ONGOING
        app.save(update_fields=['status'])
        app.initialize_construction_phases()

        return Response({
            'message': 'Construction monitoring started. Status updated to CONSTRUCTION ONGOING.',
            'application': PermitApplicationSerializer(app).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def approve_completion(self, request, pk=None):
        """
        Officer final inspection & completion approval.
        Enforces that all required construction phases are approved.
        Transitions permit to COMPLETED and generates final certificate.
        """
        user = request.user
        if user.is_municipality_officer:
            if not user.is_verified_officer:
                return Response(
                    {"error": "Your officer account is pending verification or rejected."},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif not (user.is_staff or user.role == 'ADMIN'):
            return Response(
                {"error": "Only municipality officers or administrators can approve construction completion."},
                status=status.HTTP_403_FORBIDDEN
            )

        application = self.get_object()

        if user.is_municipality_officer:
            if not user.municipality or application.municipality != user.municipality:
                return Response(
                    {"error": "You do not have jurisdiction over this application's municipality."},
                    status=status.HTTP_403_FORBIDDEN
                )

        if not application.can_complete_construction:
            return Response(
                {"error": "All required construction phases must be approved before final completion."},
                status=status.HTTP_400_BAD_REQUEST
            )

        remarks = request.data.get('remarks', 'All structural phases inspected and verified compliant.')

        with transaction.atomic():
            application.status = PermitApplication.Status.COMPLETED
            application.completed_at = timezone.now()
            application.completion_reviewed_by = user
            application.completion_remarks = remarks
            application.save()

            # Mark final completion phase as approved as well
            final_phase = application.construction_phases.filter(
                phase_type=ConstructionPhase.PhaseType.FINAL_COMPLETION
            ).first()
            if final_phase:
                final_phase.status = ConstructionPhase.PhaseStatus.APPROVED
                final_phase.approved_at = timezone.now()
                final_phase.reviewed_by = user
                final_phase.review_notes = remarks
                final_phase.save()

            # Generate completion certificate PDF
            generate_completion_certificate_pdf(application)

        return Response({
            'message': 'Construction successfully marked as COMPLETED. Final Completion Certificate generated.',
            'application': PermitApplicationSerializer(application).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def download_permit_approval_letter(self, request, pk=None):
        """
        Download the official Building Permit Approval Letter PDF.
        Generated when the officer first approves the permit application.
        """
        app = self.get_object()
        user = request.user

        if user.role == 'MATERIAL_SUPPLIER':
            return Response({"error": "Suppliers cannot access permit approval letters."}, status=status.HTTP_403_FORBIDDEN)

        if app.status not in [
            PermitApplication.Status.APPROVED,
            PermitApplication.Status.CONSTRUCTION_ONGOING,
            PermitApplication.Status.COMPLETION_PENDING,
            PermitApplication.Status.COMPLETED,
        ]:
            return Response(
                {"error": "Permit has not been approved yet."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not app.permit_approval_letter_pdf:
            # Attempt to regenerate from the most recent APPROVED decision
            approved_decision = app.decisions.filter(
                decision=PermitDecision.DecisionChoice.APPROVED
            ).first()
            if approved_decision:
                try:
                    generate_permit_approval_letter_pdf(app, approved_decision)
                except Exception as e:
                    return Response({"error": f"Could not generate approval letter: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({"error": "No approved decision found for this permit."}, status=status.HTTP_404_NOT_FOUND)

        return FileResponse(
            app.permit_approval_letter_pdf.open('rb'),
            content_type='application/pdf',
            as_attachment=False
        )

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def download_completion_certificate(self, request, pk=None):
        """
        Download the final Building Construction Completion Certificate.
        """
        app = self.get_object()

        # Authorization check
        user = request.user
        if user.role == 'MATERIAL_SUPPLIER':
            return Response({"error": "Suppliers cannot access completion certificates."}, status=status.HTTP_403_FORBIDDEN)

        if app.status != PermitApplication.Status.COMPLETED:
            return Response(
                {"error": "Construction is not yet marked as COMPLETED."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not app.completion_certificate_pdf:
            generate_completion_certificate_pdf(app)

        return FileResponse(app.completion_certificate_pdf.open('rb'), content_type='application/pdf')


class ConstructionPhaseViewSet(viewsets.ModelViewSet):
    serializer_class = ConstructionPhaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated or user.role == 'MATERIAL_SUPPLIER':
            return ConstructionPhase.objects.none()

        if user.is_staff or user.role == 'ADMIN':
            return ConstructionPhase.objects.all()

        if user.is_citizen:
            return ConstructionPhase.objects.filter(application__applicant=user)

        if user.is_municipality_officer:
            if user.is_verified_officer and user.municipality:
                return ConstructionPhase.objects.filter(application__municipality=user.municipality)
            return ConstructionPhase.objects.none()

        return ConstructionPhase.objects.none()

    def get_object(self):
        from django.shortcuts import get_object_or_404
        from rest_framework.exceptions import PermissionDenied

        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        phase = get_object_or_404(ConstructionPhase.objects.all(), **filter_kwargs)

        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied("Authentication credentials were not provided.")

        if user.is_staff or user.role == 'ADMIN':
            return phase

        if user.role == 'MATERIAL_SUPPLIER':
            raise PermissionDenied("Suppliers cannot access construction monitoring or approval documents.")

        if user.is_citizen:
            if phase.application.applicant != user:
                raise PermissionDenied("You are not authorized to access this application.")
            return phase

        if user.is_municipality_officer:
            if not user.is_verified_officer:
                raise PermissionDenied("Your officer account is pending verification or rejected.")
            if not user.municipality or phase.application.municipality != user.municipality:
                raise PermissionDenied("You do not have jurisdiction over this application's municipality.")
            return phase

        raise PermissionDenied("You do not have permission to access this resource.")

    def check_officer_permission(self, phase, user):
        """Validates that user is an authorized officer for this phase's municipality"""
        if user.is_staff or user.role == 'ADMIN':
            return None

        if user.role == 'MATERIAL_SUPPLIER':
            return Response({"error": "Suppliers cannot perform phase approvals."}, status=status.HTTP_403_FORBIDDEN)

        if not user.is_municipality_officer:
            return Response({"error": "Only municipality officers can approve or reject construction phases."}, status=status.HTTP_403_FORBIDDEN)

        if not user.is_verified_officer:
            return Response({"error": "Your officer account is pending verification."}, status=status.HTTP_403_FORBIDDEN)

        if not user.municipality or phase.application.municipality != user.municipality:
            return Response({"error": "You do not have jurisdiction over this application's municipality."}, status=status.HTTP_403_FORBIDDEN)

        return None

    @action(detail=True, methods=['post'])
    def upload_document(self, request, pk=None):
        """
        Uploads a blueprint or site photo for this construction phase.
        """
        phase = self.get_object()
        user = request.user

        if not (user.is_staff or user.role == 'ADMIN' or (
            user.is_citizen and phase.application.applicant == user
        )):
            return Response(
                {"error": "Only the citizen who owns this application can upload phase documents."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if phase.status == ConstructionPhase.PhaseStatus.APPROVED:
            return Response({"error": "Cannot upload documents to an already approved phase."}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES.get('file')
        doc_type = request.data.get('document_type', ConstructionPhaseDocument.DocumentType.BLUEPRINT)
        title = request.data.get('title', f"{phase.name} Document")

        if not file_obj:
            return Response({"error": "File is required."}, status=status.HTTP_400_BAD_REQUEST)

        doc = ConstructionPhaseDocument.objects.create(
            phase=phase,
            document_type=doc_type,
            title=title,
            file=file_obj
        )

        log_audit(
            category=AuditLog.Category.PERMIT,
            action=f"Uploaded phase document '{doc.title}' to phase {phase.sequence} of '{phase.application.reference_number}'.",
            user=user,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            status=AuditLog.Status.SUCCESS,
            metadata={'phase_id': phase.id, 'document_id': doc.id},
        )

        return Response({
            'message': 'Document uploaded successfully.',
            'document': ConstructionPhaseDocumentSerializer(doc).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """
        Citizen submits a construction phase for municipal review.
        Enforces that the previous phase must be APPROVED.
        """
        phase = self.get_object()
        user = request.user

        if user.is_citizen and phase.application.applicant != user:
            return Response({"error": "You do not own this application."}, status=status.HTTP_403_FORBIDDEN)

        if user.role == 'MATERIAL_SUPPLIER':
            return Response({"error": "Suppliers cannot submit construction phases."}, status=status.HTTP_403_FORBIDDEN)

        if phase.status == ConstructionPhase.PhaseStatus.APPROVED:
            return Response({"error": "Phase is already approved."}, status=status.HTTP_400_BAD_REQUEST)

        # Enforce prerequisite phase order
        if not phase.is_prerequisite_satisfied:
            return Response(
                {"error": "Previous construction phase must be approved before submitting this phase."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not phase.documents.exists():
            return Response(
                {"error": "Attach at least one document to this phase before submitting it for officer review."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            phase.status = ConstructionPhase.PhaseStatus.SUBMITTED
            phase.submitted_at = timezone.now()
            phase.save()

            # If application status was APPROVED, transition to CONSTRUCTION ONGOING
            app = phase.application
            if app.status == PermitApplication.Status.APPROVED:
                app.status = PermitApplication.Status.CONSTRUCTION_ONGOING
                app.save(update_fields=['status'])

            log_audit(
                category=AuditLog.Category.PERMIT,
                action=f"Submitted phase {phase.sequence} of '{app.reference_number}' for officer review.",
                user=user,
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                status=AuditLog.Status.SUCCESS,
                metadata={'phase_id': phase.id, 'document_count': phase.documents.count()},
            )

        return Response({
            'message': f'{phase.name} submitted successfully for officer review.',
            'phase': ConstructionPhaseSerializer(phase).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """
        Officer reviews, approves, or rejects a submitted construction phase.
        Enforces officer role, municipality match, phase SUBMITTED state, and prerequisite order.
        """
        phase = self.get_object()
        err_response = self.check_officer_permission(phase, request.user)
        if err_response:
            return err_response

        # Enforce that previous phase was approved
        if not phase.is_prerequisite_satisfied:
            return Response(
                {"error": "Previous construction phase must be approved before reviewing this phase."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce that this phase was actually submitted
        if phase.status != ConstructionPhase.PhaseStatus.SUBMITTED:
            return Response(
                {"error": "Phase must be in SUBMITTED status before review."},
                status=status.HTTP_400_BAD_REQUEST
            )

        decision = request.data.get('decision')
        remarks = request.data.get('remarks', '')

        if decision not in ['APPROVED', 'REJECTED']:
            return Response(
                {"error": "Invalid decision. Choose APPROVED or REJECTED."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if decision == 'APPROVED':
                phase.status = ConstructionPhase.PhaseStatus.APPROVED
                phase.approved_at = timezone.now()
                phase.reviewed_by = request.user
                phase.review_notes = remarks
                phase.save()

                # Generate phase approval PDF
                generate_phase_approval_pdf(phase)

                # If blueprint exists, stamp it
                try:
                    stamp_phase_blueprint(phase)
                except ValidationError:
                    # Stamping not possible if no blueprint file; document this
                    pass

                msg = f"{phase.name} approved successfully. Approval document generated."
            else:
                phase.status = ConstructionPhase.PhaseStatus.REJECTED
                phase.rejected_at = timezone.now()
                phase.reviewed_by = request.user
                phase.review_notes = remarks
                phase.save()
                msg = f"{phase.name} rejected with remarks: {remarks}"

        return Response({
            'message': msg,
            'phase': ConstructionPhaseSerializer(phase).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def download_approval_pdf(self, request, pk=None):
        """
        Download generated phase approval document.
        """
        phase = self.get_object()
        if request.user.role == 'MATERIAL_SUPPLIER':
            return Response({"error": "Suppliers cannot download approval documents."}, status=status.HTTP_403_FORBIDDEN)

        if phase.status != ConstructionPhase.PhaseStatus.APPROVED:
            return Response({"error": "Phase is not approved."}, status=status.HTTP_400_BAD_REQUEST)

        if not phase.generated_approval_pdf:
            generate_phase_approval_pdf(phase)

        return FileResponse(phase.generated_approval_pdf.open('rb'), content_type='application/pdf')

    @action(detail=True, methods=['get'])
    def download_stamped_blueprint(self, request, pk=None):
        """
        Download stamped approved copy of the blueprint.
        """
        phase = self.get_object()
        if request.user.role == 'MATERIAL_SUPPLIER':
            return Response({"error": "Suppliers cannot download stamped blueprints."}, status=status.HTTP_403_FORBIDDEN)

        if phase.status != ConstructionPhase.PhaseStatus.APPROVED:
            return Response({"error": "Phase is not approved."}, status=status.HTTP_400_BAD_REQUEST)

        if not phase.generated_stamped_blueprint:
            try:
                stamp_phase_blueprint(phase)
            except ValidationError as e:
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        ext = phase.generated_stamped_blueprint.name.lower()
        c_type = 'application/pdf' if ext.endswith('.pdf') else 'image/jpeg'
        return FileResponse(phase.generated_stamped_blueprint.open('rb'), content_type=c_type)

    @action(detail=True, methods=['post'])
    def stamp_blueprint(self, request, pk=None):
        """
        Explicitly triggers blueprint stamping for this phase.
        Produces controlled 400 if no blueprint exists.
        """
        phase = self.get_object()
        err_response = self.check_officer_permission(phase, request.user)
        if err_response:
            return err_response

        try:
            url = stamp_phase_blueprint(phase)
            return Response({
                'message': 'Blueprint stamped successfully.',
                'stamped_url': url,
                'phase': ConstructionPhaseSerializer(phase).data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)


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
