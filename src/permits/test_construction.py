import os
import hashlib
import io
import tempfile
import shutil
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
import pypdf
from PIL import Image

from locations.models import Province, District, Municipality, Ward
from permits.models import (
    PermitApplication,
    ApplicationDocument,
    ConstructionPhase,
    ConstructionPhaseDocument
)

User = get_user_model()

TEST_MEDIA_ROOT = tempfile.mkdtemp()


def make_dummy_pdf():
    """Generates a valid 2-page dummy PDF for blueprint testing"""
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=400, height=600)
    writer.add_blank_page(width=400, height=600)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_dummy_image():
    """Generates a valid image file for blueprint testing"""
    img = Image.new('RGB', (300, 300), color='white')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ConstructionPhaseMonitoringLifecycleTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.client = APIClient()

        # Location Setup: Bagmati / Kathmandu
        self.province_bagmati = Province.objects.create(name='Bagmati Province', code=3)
        self.district_ktm = District.objects.create(province=self.province_bagmati, name='Kathmandu')
        self.muni_ktm = Municipality.objects.create(
            district=self.district_ktm,
            name='Kathmandu Metropolitan City',
            type=Municipality.TypeChoices.METROPOLITAN
        )
        self.ward_ktm = Ward.objects.create(municipality=self.muni_ktm, ward_number=10)

        # Location Setup: Koshi / Sunsari / Dharan for dynamic municipality testing
        self.province_koshi = Province.objects.create(name='Koshi Province', code=1)
        self.district_sunsari = District.objects.create(province=self.province_koshi, name='Sunsari')
        self.muni_dharan = Municipality.objects.create(
            district=self.district_sunsari,
            name='Dharan Sub-Metropolitan City',
            type=Municipality.TypeChoices.SUB_METROPOLITAN
        )
        self.ward_dharan = Ward.objects.create(municipality=self.muni_dharan, ward_number=15)

        # Users
        self.citizen = User.objects.create_user(
            username='ram_shrestha', email='ram@test.com', password='password123',
            role=User.Role.CITIZEN, first_name='Ram', last_name='Shrestha'
        )
        self.other_citizen = User.objects.create_user(
            username='shyam_karki', email='shyam@test.com', password='password123',
            role=User.Role.CITIZEN, first_name='Shyam', last_name='Karki'
        )
        self.officer_ktm = User.objects.create_user(
            username='officer_arun', email='arun@ktm.gov.np', password='password123',
            role=User.Role.MUNICIPALITY_OFFICER, municipality=self.muni_ktm,
            verification_status=User.VerificationStatus.APPROVED,
            first_name='Arun', last_name='Adhikari'
        )
        self.officer_dharan = User.objects.create_user(
            username='officer_bikash', email='bikash@dharan.gov.np', password='password123',
            role=User.Role.MUNICIPALITY_OFFICER, municipality=self.muni_dharan,
            verification_status=User.VerificationStatus.APPROVED,
            first_name='Bikash', last_name='Rai'
        )
        self.supplier = User.objects.create_user(
            username='supplier_gorkha', email='supplier@test.com', password='password123',
            role=User.Role.MATERIAL_SUPPLIER
        )
        self.admin = User.objects.create_superuser(
            username='admin_user', email='admin@test.com', password='password123',
            role=User.Role.ADMIN
        )

        # Approved building permit (storeys_count = 2) in KTM
        self.permit_ktm = PermitApplication.objects.create(
            applicant=self.citizen,
            municipality=self.muni_ktm,
            ward=self.ward_ktm,
            tole_address='New Baneshwor, Marg 4',
            plot_number='K-9876',
            land_area_sqft=1500,
            total_built_up_area_sqft=2400,
            storeys_count=2,
            estimated_cost=7500000,
            status=PermitApplication.Status.APPROVED
        )

        # Upload initial permit blueprint
        dummy_pdf = make_dummy_pdf()
        self.permit_blueprint = ApplicationDocument.objects.create(
            application=self.permit_ktm,
            document_type=ApplicationDocument.DocumentType.BLUEPRINT,
            title='Approved Architectural Blueprint',
            file=SimpleUploadedFile('architectural_blueprint.pdf', dummy_pdf, content_type='application/pdf')
        )

        # Approved building permit in Dharan (for dynamic municipality testing)
        self.permit_dharan = PermitApplication.objects.create(
            applicant=self.citizen,
            municipality=self.muni_dharan,
            ward=self.ward_dharan,
            tole_address='Bhanuchowk',
            plot_number='DH-4321',
            land_area_sqft=1800,
            total_built_up_area_sqft=2800,
            storeys_count=1,
            estimated_cost=6000000,
            status=PermitApplication.Status.APPROVED
        )

    # -------------------------------------------------------------
    # TEST 1: Approved permit changes to CONSTRUCTION ONGOING.
    # -------------------------------------------------------------
    def test_01_approved_permit_changes_to_construction_ongoing(self):
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/start_construction/')
        self.assertEqual(res.status_code, 200)
        self.permit_ktm.refresh_from_db()
        self.assertEqual(self.permit_ktm.status, PermitApplication.Status.CONSTRUCTION_ONGOING)

    # -------------------------------------------------------------
    # TEST 2: First phase is initialized correctly.
    # -------------------------------------------------------------
    def test_02_first_phase_initialized_correctly(self):
        phases = self.permit_ktm.initialize_construction_phases()
        self.assertTrue(len(phases) >= 3)
        plinth = phases[0]
        self.assertEqual(plinth.sequence, 1)
        self.assertEqual(plinth.phase_type, ConstructionPhase.PhaseType.PLINTH)
        self.assertEqual(plinth.status, ConstructionPhase.PhaseStatus.PENDING)
        self.assertEqual(plinth.name, 'Plinth Level')

    # -------------------------------------------------------------
    # TEST 3: A phase cannot be submitted without a phase-level document.
    # -------------------------------------------------------------
    def test_03_citizen_cannot_submit_first_phase_without_document(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]

        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/submit/')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Attach at least one document', res.data.get('error', ''))
        plinth.refresh_from_db()
        self.assertEqual(plinth.status, ConstructionPhase.PhaseStatus.PENDING)
        self.assertIsNone(plinth.submitted_at)

    # -------------------------------------------------------------
    # TEST 3a: Officer review receives documents uploaded to a phase.
    # -------------------------------------------------------------
    def test_03a_officer_review_includes_citizen_phase_documents(self):
        plinth = self.permit_ktm.initialize_construction_phases()[0]

        self.client.force_authenticate(user=self.citizen)
        upload = self.client.post(
            f'/api/v1/permits/phases/{plinth.id}/upload_document/',
            {
                'title': 'Plinth reinforcement inspection photo',
                'document_type': ConstructionPhaseDocument.DocumentType.SITE_PHOTO,
                'file': SimpleUploadedFile(
                    'plinth-photo.jpg', make_dummy_image(), content_type='image/jpeg'
                ),
            },
            format='multipart',
        )
        self.assertEqual(upload.status_code, 201)
        self.assertEqual(upload.data['document']['phase'], plinth.id)
        self.assertEqual(self.client.post(f'/api/v1/permits/phases/{plinth.id}/submit/').status_code, 200)

        self.client.force_authenticate(user=self.officer_ktm)
        application_response = self.client.get(f'/api/v1/permits/applications/{self.permit_ktm.id}/')
        self.assertEqual(application_response.status_code, 200)
        reviewed_phase = next(
            phase for phase in application_response.data['construction_phases']
            if phase['id'] == plinth.id
        )
        self.assertEqual(len(reviewed_phase['documents']), 1)
        self.assertEqual(reviewed_phase['documents'][0]['title'], 'Plinth reinforcement inspection photo')

        phase_response = self.client.get(f'/api/v1/permits/phases/{plinth.id}/')
        self.assertEqual(phase_response.status_code, 200)
        self.assertEqual(len(phase_response.data['documents']), 1)

    # -------------------------------------------------------------
    # TEST 3b: A citizen can add a file to a phase already submitted.
    # -------------------------------------------------------------
    def test_03b_citizen_can_attach_document_to_submitted_phase(self):
        plinth = self.permit_ktm.initialize_construction_phases()[0]
        ConstructionPhaseDocument.objects.create(
            phase=plinth,
            document_type=ConstructionPhaseDocument.DocumentType.BLUEPRINT,
            title='Initial plinth blueprint',
            file=SimpleUploadedFile('plinth-blueprint.jpg', make_dummy_image(), content_type='image/jpeg'),
        )
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.citizen)
        response = self.client.post(
            f'/api/v1/permits/phases/{plinth.id}/upload_document/',
            {
                'title': 'Plinth concrete progress photo',
                'document_type': ConstructionPhaseDocument.DocumentType.SITE_PHOTO,
                'file': SimpleUploadedFile('plinth-progress.jpg', make_dummy_image(), content_type='image/jpeg'),
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['document']['phase'], plinth.id)

        self.client.force_authenticate(user=self.officer_ktm)
        response = self.client.get(f'/api/v1/permits/phases/{plinth.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['documents']), 2)

    # -------------------------------------------------------------
    # TEST 4: Officer can review submitted phase.
    # -------------------------------------------------------------
    def test_04_officer_can_review_submitted_phase(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Plinth level verified on site. Concrete strength test certified.'
        })
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------
    # TEST 5: Authorized officer can approve phase.
    # -------------------------------------------------------------
    def test_05_authorized_officer_can_approve_phase(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved by Kathmandu Metropolitan Officer.'
        })
        self.assertEqual(res.status_code, 200)
        plinth.refresh_from_db()
        self.assertEqual(plinth.status, ConstructionPhase.PhaseStatus.APPROVED)
        self.assertEqual(plinth.reviewed_by, self.officer_ktm)
        self.assertIsNotNone(plinth.approved_at)

    # -------------------------------------------------------------
    # TEST 6: Unauthorized officer cannot approve phase.
    # -------------------------------------------------------------
    def test_06_unauthorized_officer_cannot_approve_phase(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        # Dharan officer has no jurisdiction over KTM permit
        self.client.force_authenticate(user=self.officer_dharan)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Unauthorized attempt'
        })
        self.assertEqual(res.status_code, 403)
        plinth.refresh_from_db()
        self.assertEqual(plinth.status, ConstructionPhase.PhaseStatus.SUBMITTED)

    # -------------------------------------------------------------
    # TEST 7: Citizen cannot approve phase.
    # -------------------------------------------------------------
    def test_07_citizen_cannot_approve_phase(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Citizen self-approval attempt'
        })
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # TEST 8: Supplier cannot access phase approval.
    # -------------------------------------------------------------
    def test_08_supplier_cannot_access_phase_approval(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.supplier)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Supplier approval attempt'
        })
        self.assertEqual(res.status_code, 403)

    # -------------------------------------------------------------
    # TEST 9: Second phase cannot be submitted before first phase approval.
    # -------------------------------------------------------------
    def test_09_second_phase_cannot_be_submitted_before_first_phase_approval(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        first_floor = phases[1]

        # Plinth is still PENDING
        self.assertEqual(plinth.status, ConstructionPhase.PhaseStatus.PENDING)

        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/phases/{first_floor.id}/submit/')
        self.assertEqual(res.status_code, 400)
        self.assertIn('Previous construction phase must be approved', res.data.get('error', ''))

    # -------------------------------------------------------------
    # TEST 10: Second phase can be submitted after first phase approval.
    # -------------------------------------------------------------
    def test_10_second_phase_can_be_submitted_after_first_phase_approval(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        first_floor = phases[1]

        # Approve plinth
        plinth.status = ConstructionPhase.PhaseStatus.APPROVED
        plinth.approved_at = self.permit_ktm.created_at
        plinth.save()
        ConstructionPhaseDocument.objects.create(
            phase=first_floor,
            document_type=ConstructionPhaseDocument.DocumentType.BLUEPRINT,
            title='First floor blueprint',
            file=SimpleUploadedFile('first-floor.jpg', make_dummy_image(), content_type='image/jpeg'),
        )

        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/phases/{first_floor.id}/submit/')
        self.assertEqual(res.status_code, 200)
        first_floor.refresh_from_db()
        self.assertEqual(first_floor.status, ConstructionPhase.PhaseStatus.SUBMITTED)

    # -------------------------------------------------------------
    # TEST 11: Rejected phase cannot advance to the next phase.
    # -------------------------------------------------------------
    def test_11_rejected_phase_cannot_advance_to_the_next_phase(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        first_floor = phases[1]

        plinth.status = ConstructionPhase.PhaseStatus.REJECTED
        plinth.review_notes = 'Pillar reinforcement deficient.'
        plinth.save()

        # Cannot submit next phase
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/phases/{first_floor.id}/submit/')
        self.assertEqual(res.status_code, 400)

    # -------------------------------------------------------------
    # TEST 12: Rejected phase can be resubmitted where appropriate.
    # -------------------------------------------------------------
    def test_12_rejected_phase_can_be_resubmitted(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.REJECTED
        plinth.save()
        ConstructionPhaseDocument.objects.create(
            phase=plinth,
            document_type=ConstructionPhaseDocument.DocumentType.SITE_PHOTO,
            title='Corrected plinth photo',
            file=SimpleUploadedFile('corrected-plinth.jpg', make_dummy_image(), content_type='image/jpeg'),
        )

        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/submit/')
        self.assertEqual(res.status_code, 200)
        plinth.refresh_from_db()
        self.assertEqual(plinth.status, ConstructionPhase.PhaseStatus.SUBMITTED)

    # -------------------------------------------------------------
    # TEST 13: Approved phase generates its approval PDF.
    # -------------------------------------------------------------
    def test_13_approved_phase_generates_approval_pdf(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        self.assertEqual(res.status_code, 200)
        plinth.refresh_from_db()
        self.assertTrue(bool(plinth.generated_approval_pdf))
        self.assertTrue(os.path.exists(plinth.generated_approval_pdf.path))

    # -------------------------------------------------------------
    # TEST 14: Generated PDF contains correct municipality.
    # -------------------------------------------------------------
    def test_14_generated_pdf_contains_correct_municipality(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        reader = pypdf.PdfReader(plinth.generated_approval_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn("KATHMANDU METROPOLITAN CITY", extracted_text.upper())

    # -------------------------------------------------------------
    # TEST 15: Generated PDF contains correct applicant.
    # -------------------------------------------------------------
    def test_15_generated_pdf_contains_correct_applicant(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        reader = pypdf.PdfReader(plinth.generated_approval_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn("Ram Shrestha", extracted_text)

    # -------------------------------------------------------------
    # TEST 16: Generated PDF contains correct permit number.
    # -------------------------------------------------------------
    def test_16_generated_pdf_contains_correct_permit_number(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        reader = pypdf.PdfReader(plinth.generated_approval_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn(self.permit_ktm.reference_number, extracted_text)

    # -------------------------------------------------------------
    # TEST 17: Generated PDF contains correct phase.
    # -------------------------------------------------------------
    def test_17_generated_pdf_contains_correct_phase(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        reader = pypdf.PdfReader(plinth.generated_approval_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn("PLINTH LEVEL", extracted_text.upper())

    # -------------------------------------------------------------
    # TEST 18: Generated PDF contains correct approving officer.
    # -------------------------------------------------------------
    def test_18_generated_pdf_contains_correct_approving_officer(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        reader = pypdf.PdfReader(plinth.generated_approval_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn("Arun Adhikari", extracted_text)

    # -------------------------------------------------------------
    # TEST 19: Original uploaded blueprint remains unchanged.
    # -------------------------------------------------------------
    def test_19_original_uploaded_blueprint_remains_unchanged(self):
        orig_path = self.permit_blueprint.file.path
        with open(orig_path, 'rb') as f:
            orig_hash = hashlib.sha256(f.read()).hexdigest()
        orig_size = os.path.getsize(orig_path)

        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })

        with open(orig_path, 'rb') as f:
            new_hash = hashlib.sha256(f.read()).hexdigest()
        new_size = os.path.getsize(orig_path)

        self.assertEqual(orig_hash, new_hash, "Original blueprint file was altered!")
        self.assertEqual(orig_size, new_size, "Original blueprint file size changed!")

    # -------------------------------------------------------------
    # TEST 20: Stamped blueprint is generated separately.
    # -------------------------------------------------------------
    def test_20_stamped_blueprint_is_generated_separately(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        self.assertTrue(bool(plinth.generated_stamped_blueprint))
        stamped_path = plinth.generated_stamped_blueprint.path
        orig_path = self.permit_blueprint.file.path

        self.assertNotEqual(stamped_path, orig_path)
        self.assertTrue(os.path.exists(stamped_path))
        self.assertTrue(os.path.exists(orig_path))

    # -------------------------------------------------------------
    # TEST 21: Final completion cannot occur before all required phases are approved.
    # -------------------------------------------------------------
    def test_21_final_completion_cannot_occur_before_all_required_phases_approved(self):
        phases = self.permit_ktm.initialize_construction_phases()
        # Plinth is approved, but First Floor and Second Floor are still PENDING
        phases[0].status = ConstructionPhase.PhaseStatus.APPROVED
        phases[0].save()

        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/approve_completion/', {
            'remarks': 'Completion premature attempt'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("All required construction phases must be approved", res.data.get('error', ''))

    # -------------------------------------------------------------
    # TEST 22: Final completion can occur after all required phases are approved.
    # -------------------------------------------------------------
    def test_22_final_completion_can_occur_after_all_phases_approved(self):
        phases = self.permit_ktm.initialize_construction_phases()
        # Mark all structural phases (Plinth, 1st, 2nd) as APPROVED
        for p in phases[:-1]:
            p.status = ConstructionPhase.PhaseStatus.APPROVED
            p.approved_at = self.permit_ktm.created_at
            p.reviewed_by = self.officer_ktm
            p.save()

        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/approve_completion/', {
            'remarks': 'Final site audit completed satisfactorily.'
        })
        self.assertEqual(res.status_code, 200)
        self.permit_ktm.refresh_from_db()
        self.assertEqual(self.permit_ktm.status, PermitApplication.Status.COMPLETED)
        self.assertIsNotNone(self.permit_ktm.completed_at)
        self.assertEqual(self.permit_ktm.completion_reviewed_by, self.officer_ktm)

    # -------------------------------------------------------------
    # TEST 23: Final completion certificate is generated.
    # -------------------------------------------------------------
    def test_23_final_completion_certificate_is_generated(self):
        phases = self.permit_ktm.initialize_construction_phases()
        for p in phases[:-1]:
            p.status = ConstructionPhase.PhaseStatus.APPROVED
            p.approved_at = self.permit_ktm.created_at
            p.reviewed_by = self.officer_ktm
            p.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/approve_completion/', {
            'remarks': 'Certified'
        })
        self.permit_ktm.refresh_from_db()

        self.assertTrue(bool(self.permit_ktm.completion_certificate_pdf))
        self.assertTrue(os.path.exists(self.permit_ktm.completion_certificate_pdf.path))

    # -------------------------------------------------------------
    # TEST 24: Final certificate contains phase approval history.
    # -------------------------------------------------------------
    def test_24_final_certificate_contains_phase_approval_history(self):
        phases = self.permit_ktm.initialize_construction_phases()
        for p in phases[:-1]:
            p.status = ConstructionPhase.PhaseStatus.APPROVED
            p.approved_at = self.permit_ktm.created_at
            p.reviewed_by = self.officer_ktm
            p.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/approve_completion/', {
            'remarks': 'Certified'
        })
        self.permit_ktm.refresh_from_db()

        reader = pypdf.PdfReader(self.permit_ktm.completion_certificate_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn("Plinth Level", extracted_text)
        self.assertIn("First Floor", extracted_text)
        self.assertIn("Second Floor", extracted_text)

    # -------------------------------------------------------------
    # TEST 25: Final certificate contains correct municipality.
    # -------------------------------------------------------------
    def test_25_final_certificate_contains_correct_municipality(self):
        # Test Dharan Permit Completion
        phases_dharan = self.permit_dharan.initialize_construction_phases()
        for p in phases_dharan[:-1]:
            p.status = ConstructionPhase.PhaseStatus.APPROVED
            p.approved_at = self.permit_dharan.created_at
            p.reviewed_by = self.officer_dharan
            p.save()

        self.client.force_authenticate(user=self.officer_dharan)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_dharan.id}/approve_completion/', {
            'remarks': 'Dharan construction completed.'
        })
        self.assertEqual(res.status_code, 200)
        self.permit_dharan.refresh_from_db()

        reader = pypdf.PdfReader(self.permit_dharan.completion_certificate_pdf.path)
        extracted_text = " ".join([page.extract_text() for page in reader.pages])
        self.assertIn("DHARAN SUB-METROPOLITAN CITY", extracted_text.upper())
        self.assertIn("SUNSARI", extracted_text.upper())
        self.assertIn("KOSHI PROVINCE", extracted_text.upper())

    # -------------------------------------------------------------
    # TEST 26: Citizen can download generated approved documents.
    # -------------------------------------------------------------
    def test_26_citizen_can_download_generated_approved_documents(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })
        plinth.refresh_from_db()

        # Citizen downloads
        self.client.force_authenticate(user=self.citizen)
        res = self.client.get(f'/api/v1/permits/phases/{plinth.id}/download_approval_pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')

    # -------------------------------------------------------------
    # TEST 27: Unauthorized users cannot download restricted documents.
    # -------------------------------------------------------------
    def test_27_unauthorized_users_cannot_download_restricted_documents(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        plinth.status = ConstructionPhase.PhaseStatus.SUBMITTED
        plinth.save()

        self.client.force_authenticate(user=self.officer_ktm)
        self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Approved'
        })

        # Other citizen cannot download Ram's document
        self.client.force_authenticate(user=self.other_citizen)
        res = self.client.get(f'/api/v1/permits/phases/{plinth.id}/download_approval_pdf/')
        self.assertIn(res.status_code, [403, 404])

        # Supplier cannot download
        self.client.force_authenticate(user=self.supplier)
        res_supplier = self.client.get(f'/api/v1/permits/phases/{plinth.id}/download_approval_pdf/')
        self.assertIn(res_supplier.status_code, [403, 404])

    # -------------------------------------------------------------
    # TEST 28: Missing blueprint produces controlled HTTP 400 response.
    # -------------------------------------------------------------
    def test_28_missing_blueprint_produces_controlled_http_400(self):
        # Create a new permit with NO blueprint documents
        empty_permit = PermitApplication.objects.create(
            applicant=self.citizen,
            municipality=self.muni_ktm,
            ward=self.ward_ktm,
            tole_address='Baneshwor',
            plot_number='K-EMPTY',
            land_area_sqft=1200,
            total_built_up_area_sqft=1800,
            storeys_count=1,
            estimated_cost=4000000,
            status=PermitApplication.Status.APPROVED
        )
        phases = empty_permit.initialize_construction_phases()
        plinth = phases[0]

        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/stamp_blueprint/')
        self.assertEqual(res.status_code, 400)
        self.assertIn("No architectural blueprint has been submitted", res.data.get('error', ''))

    # -------------------------------------------------------------
    # TEST 29: Invalid phase transition produces controlled HTTP 400 response.
    # -------------------------------------------------------------
    def test_29_invalid_phase_transition_produces_controlled_http_400(self):
        phases = self.permit_ktm.initialize_construction_phases()
        plinth = phases[0]
        # Trying to review while still in PENDING status (not SUBMITTED)
        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.post(f'/api/v1/permits/phases/{plinth.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Cannot review unsubmitted phase'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("Phase must be in SUBMITTED status before review", res.data.get('error', ''))

    # -------------------------------------------------------------
    # TEST 30: Existing permit functionality still works.
    # -------------------------------------------------------------
    def test_30_existing_permit_functionality_still_works(self):
        self.client.force_authenticate(user=self.citizen)
        res = self.client.get('/api/v1/permits/applications/')
        self.assertEqual(res.status_code, 200)
        items = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertTrue(len(items) >= 2)

    # -------------------------------------------------------------
    # TEST 31: Existing authentication/RBAC tests still pass.
    # -------------------------------------------------------------
    def test_31_existing_authentication_and_rbac_enforced(self):
        self.client.force_authenticate(user=self.officer_ktm)
        res = self.client.get(f'/api/v1/permits/applications/{self.permit_dharan.id}/')
        # KTM officer cannot see or access Dharan permit
        self.assertIn(res.status_code, [403, 404])

    # -------------------------------------------------------------
    # TEST 32: Existing marketplace/order/payment tests still pass.
    # -------------------------------------------------------------
    def test_32_marketplace_and_other_modules_accessible(self):
        self.client.force_authenticate(user=self.citizen)
        res = self.client.get('/api/v1/marketplace/products/')
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------
    # TEST 33: Construction phases match submitted storeys from application form.
    # -------------------------------------------------------------
    def test_33_phases_match_submitted_storeys_from_application_form(self):
        self.client.force_authenticate(user=self.citizen)

        # 1-storey building -> 3 phases (Plinth, First Floor, Final Completion)
        res1 = self.client.post('/api/v1/permits/applications/', {
            'application_type': 'NEW_CONSTRUCTION',
            'municipality': self.muni_ktm.id,
            'ward': self.ward_ktm.id,
            'tole_address': 'Baneshwor Height',
            'plot_number': 'PL-101',
            'land_area_sqft': 1200,
            'total_built_up_area_sqft': 1000,
            'storeys_count': 1,
            'estimated_cost': 3500000
        }, format='json')
        self.assertEqual(res1.status_code, 201)
        app1 = PermitApplication.objects.get(id=res1.data['id'])
        phases1 = list(app1.construction_phases.all())
        self.assertEqual(len(phases1), 3)
        self.assertEqual([p.name for p in phases1], ['Plinth Level', 'First Floor', 'Final Completion Inspection'])

        # 3-storey building -> 5 phases (Plinth, 1st, 2nd, 3rd, Final Completion)
        res3 = self.client.post('/api/v1/permits/applications/', {
            'application_type': 'NEW_CONSTRUCTION',
            'municipality': self.muni_ktm.id,
            'ward': self.ward_ktm.id,
            'tole_address': 'Shantinagar Marg',
            'plot_number': 'PL-303',
            'land_area_sqft': 2000,
            'total_built_up_area_sqft': 3500,
            'storeys_count': 3,
            'estimated_cost': 12000000
        }, format='json')
        self.assertEqual(res3.status_code, 201)
        app3 = PermitApplication.objects.get(id=res3.data['id'])
        phases3 = list(app3.construction_phases.all())
        self.assertEqual(len(phases3), 5)
        self.assertEqual([p.name for p in phases3], ['Plinth Level', 'First Floor', 'Second Floor', 'Third Floor', 'Final Completion Inspection'])

        # 4-storey building -> 6 phases (Plinth, 1st, 2nd, 3rd, 4th, Final Completion)
        res4 = self.client.post('/api/v1/permits/applications/', {
            'application_type': 'NEW_CONSTRUCTION',
            'municipality': self.muni_ktm.id,
            'ward': self.ward_ktm.id,
            'tole_address': 'Koteshwor Chowk',
            'plot_number': 'PL-404',
            'land_area_sqft': 2500,
            'total_built_up_area_sqft': 4800,
            'storeys_count': 4,
            'estimated_cost': 18000000
        }, format='json')
        self.assertEqual(res4.status_code, 201)
        app4 = PermitApplication.objects.get(id=res4.data['id'])
        phases4 = list(app4.construction_phases.all())
        self.assertEqual(len(phases4), 6)
        self.assertEqual([p.name for p in phases4], ['Plinth Level', 'First Floor', 'Second Floor', 'Third Floor', 'Fourth Floor', 'Final Completion Inspection'])
