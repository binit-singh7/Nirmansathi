from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from locations.models import Province, District, Municipality

User = get_user_model()

class OfficerVerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.province = Province.objects.create(name='Bagmati', code=3)
        self.district = District.objects.create(province=self.province, name='Kathmandu')
        self.muni = Municipality.objects.create(district=self.district, name='Kathmandu Metropolitan City')

        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='password123',
            role=User.Role.ADMIN,
            is_staff=True
        )
        self.citizen = User.objects.create_user(
            username='citizen_test',
            email='citizen@test.com',
            password='password123',
            role=User.Role.CITIZEN
        )

    def test_officer_registration_sets_pending(self):
        payload = {
            'username': 'new_officer',
            'email': 'new_officer@test.com',
            'password': 'password123',
            'role': 'MUNICIPALITY_OFFICER',
            'municipality': self.muni.id
        }
        res = self.client.post('/api/v1/accounts/register/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        officer = User.objects.get(username='new_officer')
        self.assertEqual(officer.verification_status, User.VerificationStatus.PENDING)
        self.assertFalse(officer.is_verified_officer)

    def test_citizen_registration_sets_not_applicable(self):
        payload = {
            'username': 'new_citizen',
            'email': 'new_citizen@test.com',
            'password': 'password123',
            'role': 'CITIZEN'
        }
        res = self.client.post('/api/v1/accounts/register/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        user = User.objects.get(username='new_citizen')
        self.assertEqual(user.verification_status, User.VerificationStatus.NOT_APPLICABLE)
        self.assertFalse(user.is_verified_officer)

    def test_admin_can_approve_officer(self):
        officer = User.objects.create_user(
            username='pending_officer',
            email='pending@test.com',
            password='password123',
            role=User.Role.MUNICIPALITY_OFFICER,
            municipality=self.muni,
            verification_status=User.VerificationStatus.PENDING
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(f'/api/v1/accounts/officers/{officer.id}/verify/', {'action': 'APPROVE'}, format='json')
        self.assertEqual(res.status_code, 200)
        officer.refresh_from_db()
        self.assertEqual(officer.verification_status, User.VerificationStatus.APPROVED)
        self.assertTrue(officer.is_verified_officer)
        self.assertEqual(officer.verified_by, self.admin)
        self.assertIsNotNone(officer.verified_at)

    def test_admin_can_reject_officer(self):
        officer = User.objects.create_user(
            username='pending_officer2',
            email='pending2@test.com',
            password='password123',
            role=User.Role.MUNICIPALITY_OFFICER,
            municipality=self.muni,
            verification_status=User.VerificationStatus.PENDING
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            f'/api/v1/accounts/officers/{officer.id}/verify/',
            {'action': 'REJECT', 'rejection_reason': 'Invalid credentials'},
            format='json'
        )
        self.assertEqual(res.status_code, 200)
        officer.refresh_from_db()
        self.assertEqual(officer.verification_status, User.VerificationStatus.REJECTED)
        self.assertFalse(officer.is_verified_officer)
        self.assertEqual(officer.rejection_reason, 'Invalid credentials')

    def test_rejection_requires_reason(self):
        officer = User.objects.create_user(
            username='pending_officer3',
            email='pending3@test.com',
            password='password123',
            role=User.Role.MUNICIPALITY_OFFICER,
            municipality=self.muni,
            verification_status=User.VerificationStatus.PENDING
        )
        self.client.force_authenticate(user=self.admin)
        res = self.client.post(
            f'/api/v1/accounts/officers/{officer.id}/verify/',
            {'action': 'REJECT', 'rejection_reason': ''},
            format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_non_admin_cannot_verify_officer(self):
        officer = User.objects.create_user(
            username='pending_officer4',
            email='pending4@test.com',
            password='password123',
            role=User.Role.MUNICIPALITY_OFFICER,
            municipality=self.muni,
            verification_status=User.VerificationStatus.PENDING
        )
        self.client.force_authenticate(user=self.citizen)
        res = self.client.post(f'/api/v1/accounts/officers/{officer.id}/verify/', {'action': 'APPROVE'}, format='json')
        self.assertEqual(res.status_code, 403)
