from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from locations.models import Province, District, Municipality, Ward
from permits.models import PermitApplication

User = get_user_model()

class PermitOfficerAuthorizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.province = Province.objects.create(name='Bagmati', code=3)
        self.district = District.objects.create(province=self.province, name='Kathmandu')
        self.muni_ktm = Municipality.objects.create(district=self.district, name='Kathmandu Metropolitan City')
        self.muni_lalitpur = Municipality.objects.create(district=self.district, name='Lalitpur Metropolitan City')

        self.ward_ktm = Ward.objects.create(municipality=self.muni_ktm, ward_number=1)
        self.ward_lalitpur = Ward.objects.create(municipality=self.muni_lalitpur, ward_number=1)

        self.citizen = User.objects.create_user(
            username='citizen_user', email='citizen@test.com', password='password123', role=User.Role.CITIZEN
        )

        # Approved officer in KTM
        self.officer_approved_ktm = User.objects.create_user(
            username='officer_approved_ktm', email='officer_ktm@test.com', password='password123',
            role=User.Role.MUNICIPALITY_OFFICER, municipality=self.muni_ktm,
            verification_status=User.VerificationStatus.APPROVED
        )

        # Pending officer in KTM
        self.officer_pending_ktm = User.objects.create_user(
            username='officer_pending_ktm', email='officer_pending@test.com', password='password123',
            role=User.Role.MUNICIPALITY_OFFICER, municipality=self.muni_ktm,
            verification_status=User.VerificationStatus.PENDING
        )

        # Rejected officer in KTM
        self.officer_rejected_ktm = User.objects.create_user(
            username='officer_rejected_ktm', email='officer_rejected@test.com', password='password123',
            role=User.Role.MUNICIPALITY_OFFICER, municipality=self.muni_ktm,
            verification_status=User.VerificationStatus.REJECTED
        )

        # Approved officer without municipality
        self.officer_no_muni = User.objects.create_user(
            username='officer_no_muni', email='officer_no_muni@test.com', password='password123',
            role=User.Role.MUNICIPALITY_OFFICER, municipality=None,
            verification_status=User.VerificationStatus.APPROVED
        )

        # Permit in KTM
        self.permit_ktm = PermitApplication.objects.create(
            applicant=self.citizen,
            municipality=self.muni_ktm,
            ward=self.ward_ktm,
            tole_address='Baneshwor',
            plot_number='K-101',
            land_area_sqft=1200,
            total_built_up_area_sqft=2000,
            storeys_count=2,
            estimated_cost=5000000,
            status=PermitApplication.Status.PENDING
        )

        # Permit in Lalitpur
        self.permit_lalitpur = PermitApplication.objects.create(
            applicant=self.citizen,
            municipality=self.muni_lalitpur,
            ward=self.ward_lalitpur,
            tole_address='Patan',
            plot_number='P-202',
            land_area_sqft=1400,
            total_built_up_area_sqft=2200,
            storeys_count=2,
            estimated_cost=6000000,
            status=PermitApplication.Status.PENDING
        )

    def test_pending_officer_cannot_see_applications(self):
        self.client.force_authenticate(user=self.officer_pending_ktm)
        res = self.client.get('/api/v1/permits/applications/')
        self.assertEqual(res.status_code, 200)
        items = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertEqual(len(items), 0)

    def test_rejected_officer_cannot_see_applications(self):
        self.client.force_authenticate(user=self.officer_rejected_ktm)
        res = self.client.get('/api/v1/permits/applications/')
        self.assertEqual(res.status_code, 200)
        items = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertEqual(len(items), 0)

    def test_officer_without_municipality_cannot_see_applications(self):
        self.client.force_authenticate(user=self.officer_no_muni)
        res = self.client.get('/api/v1/permits/applications/')
        self.assertEqual(res.status_code, 200)
        items = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertEqual(len(items), 0)

    def test_approved_officer_sees_only_own_municipality_permits(self):
        self.client.force_authenticate(user=self.officer_approved_ktm)
        res = self.client.get('/api/v1/permits/applications/')
        self.assertEqual(res.status_code, 200)
        items = res.data if isinstance(res.data, list) else res.data.get('results', [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], self.permit_ktm.id)

    def test_pending_officer_cannot_review(self):
        self.client.force_authenticate(user=self.officer_pending_ktm)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Test'
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_rejected_officer_cannot_review(self):
        self.client.force_authenticate(user=self.officer_rejected_ktm)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Test'
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_officer_cannot_review_other_municipality_permit(self):
        self.client.force_authenticate(user=self.officer_approved_ktm)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_lalitpur.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Test'
        }, format='json')
        self.assertIn(res.status_code, (403, 404))

    def test_approved_officer_can_review_own_municipality_permit(self):
        self.client.force_authenticate(user=self.officer_approved_ktm)
        res = self.client.post(f'/api/v1/permits/applications/{self.permit_ktm.id}/review/', {
            'decision': 'APPROVED',
            'remarks': 'Fully compliant with Kathmandu bylaws.'
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.permit_ktm.refresh_from_db()
        self.assertEqual(self.permit_ktm.status, PermitApplication.Status.APPROVED)
