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


# ---------------------------------------------------------------------------
# NID OCR Utility Unit Tests
# ---------------------------------------------------------------------------

class NIDOCRUtilsTests(TestCase):
    """Unit tests for normalize_nid() and extract_nid_candidates()."""

    def test_normalize_exact(self):
        from accounts.utils import normalize_nid
        self.assertEqual(normalize_nid('12-34-56-78901'), '12-34-56-78901')

    def test_normalize_spaces_around_hyphens(self):
        from accounts.utils import normalize_nid
        self.assertEqual(normalize_nid('12 - 34 - 56 - 78901'), '12-34-56-78901')

    def test_normalize_trailing_spaces(self):
        from accounts.utils import normalize_nid
        self.assertEqual(normalize_nid('  12-34-56-78901  '), '12-34-56-78901')

    def test_normalize_different_numbers_not_equal(self):
        from accounts.utils import normalize_nid
        self.assertNotEqual(normalize_nid('12-34-56-78901'), normalize_nid('12-34-56-78902'))

    def test_normalize_hyphen_vs_no_hyphen_not_equal(self):
        """'12-34-56-78901' and '12345678901' are different IDs — must not match."""
        from accounts.utils import normalize_nid
        self.assertNotEqual(normalize_nid('12-34-56-78901'), normalize_nid('12345678901'))

    def test_extract_finds_citizenship_format(self):
        from accounts.utils import extract_nid_candidates, normalize_nid
        text = "Name: Ram Shrestha\nCitizenship No: 12-34-56-78901\nDOB: 2045"
        candidates = extract_nid_candidates(text)
        norms = [normalize_nid(c) for c in candidates]
        self.assertIn('12-34-56-78901', norms)

    def test_extract_finds_spaced_hyphen_format(self):
        from accounts.utils import extract_nid_candidates, normalize_nid
        text = "ID: 12 - 34 - 56 - 78901"
        candidates = extract_nid_candidates(text)
        norms = [normalize_nid(c) for c in candidates]
        self.assertIn('12-34-56-78901', norms)

    def test_extract_empty_text(self):
        from accounts.utils import extract_nid_candidates
        self.assertEqual(extract_nid_candidates(''), [])
        self.assertEqual(extract_nid_candidates(None), [])


# ---------------------------------------------------------------------------
# NID OCR Verification Endpoint Tests
# ---------------------------------------------------------------------------

class NIDOCRVerificationTests(TestCase):
    """
    Tests for POST /api/v1/accounts/nid/verify/

    All calls to pytesseract.image_to_string are mocked so the test suite
    runs without the Tesseract binary installed.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='ocr_test_user',
            email='ocr@test.com',
            password='password123',
            role=User.Role.CITIZEN,
        )
        self.client.force_authenticate(user=self.user)
        self.url = '/api/v1/accounts/nid/verify/'

    def _make_fake_image(self):
        """Return a minimal valid PNG byte stream as an in-memory file."""
        import io
        from PIL import Image as PILImage
        buf = io.BytesIO()
        img = PILImage.new('RGB', (10, 10), color=(255, 255, 255))
        img.save(buf, format='PNG')
        buf.seek(0)
        buf.name = 'test_nid.png'
        return buf

    # 1. Exact match
    def test_exact_match(self):
        from unittest.mock import patch
        fake_ocr = "Name: Ram Shrestha\nCitizenship No: 12-34-56-78901\n"
        with patch('accounts.utils.pytesseract') as mock_tess:
            mock_tess.image_to_string.return_value = fake_ocr
            res = self.client.post(self.url, {
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
            }, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['matched'])

    # 2. Hyphen/spacing variation
    def test_hyphen_spacing_variation(self):
        from unittest.mock import patch
        # OCR outputs spaces around hyphens; user enters clean form
        fake_ocr = "Citizenship No: 12 - 34 - 56 - 78901"
        with patch('accounts.utils.pytesseract') as mock_tess:
            mock_tess.image_to_string.return_value = fake_ocr
            res = self.client.post(self.url, {
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
            }, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['matched'])

    # 3. Wrong number — must not match
    def test_wrong_number(self):
        from unittest.mock import patch
        fake_ocr = "Citizenship No: 12-34-56-78901"
        with patch('accounts.utils.pytesseract') as mock_tess:
            mock_tess.image_to_string.return_value = fake_ocr
            res = self.client.post(self.url, {
                'citizenship_number': '12-34-56-78902',  # last digit differs
                'nid_document': self._make_fake_image(),
            }, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['matched'])

    # 4. OCR unable to detect any number (blank text)
    def test_ocr_cannot_detect_number(self):
        from unittest.mock import patch
        fake_ocr = ""  # no text detected
        with patch('accounts.utils.pytesseract') as mock_tess:
            mock_tess.image_to_string.return_value = fake_ocr
            res = self.client.post(self.url, {
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
            }, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['matched'])

    # 4b. OCR raises TesseractNotFoundError
    def test_ocr_tesseract_not_found(self):
        from unittest.mock import patch
        import pytesseract
        with patch('accounts.utils.perform_ocr_on_image',
                   side_effect=pytesseract.pytesseract.TesseractNotFoundError):
            res = self.client.post(self.url, {
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
            }, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['matched'])

    # 5. Missing citizenship_number → 400
    def test_missing_citizenship_number(self):
        res = self.client.post(self.url, {
            'nid_document': self._make_fake_image(),
        }, format='multipart')
        self.assertEqual(res.status_code, 400)

    # 6. Missing nid_document → 400
    def test_missing_nid_document(self):
        res = self.client.post(self.url, {
            'citizenship_number': '12-34-56-78901',
        }, format='multipart')
        self.assertEqual(res.status_code, 400)

    # 7. Frontend tampering: unauthenticated request (no token) must be rejected
    def test_unauthenticated_request_rejected(self):
        unauth_client = APIClient()
        res = unauth_client.post(self.url, {
            'citizenship_number': '12-34-56-78901',
            'nid_document': self._make_fake_image(),
        }, format='multipart')
        self.assertEqual(res.status_code, 401)

    # 8. Frontend tampering: registration with nid_verified=true in payload is ignored
    def test_registration_rejects_unmatched_nid_document(self):
        """
        Even if a client sends ocr_verified=true or nid_verified=true in the payload,
        the server must never trust it. nid_verified is set only by server OCR.
        """
        from unittest.mock import patch
        # Mock OCR to return non-matching text so OCR match will fail
        fake_ocr = "Some random text without any ID number"
        with patch('accounts.utils.perform_ocr_on_image', return_value=fake_ocr):
            payload = {
                'username': 'tamper_user',
                'email': 'tamper@test.com',
                'password': 'password123',
                'role': 'CITIZEN',
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
                # Attacker tries to force nid_verified=True
                'nid_verified': True,
                'ocr_verified': True,
            }
            anon_client = APIClient()
            res = anon_client.post('/api/v1/accounts/register/', payload, format='multipart')

        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(username='tamper_user').exists())

    def test_registration_marks_matching_nid_document_verified(self):
        from unittest.mock import patch
        with patch(
            'accounts.utils.perform_ocr_on_image',
            return_value='Citizenship No: 12-34-56-78901',
        ):
            res = APIClient().post('/api/v1/accounts/register/', {
                'username': 'verified_nid_user',
                'email': 'verified-nid@test.com',
                'password': 'password123',
                'role': 'CITIZEN',
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
            }, format='multipart')

        self.assertEqual(res.status_code, 201)
        user = User.objects.get(username='verified_nid_user')
        self.assertTrue(user.profile.nid_verified)

    def test_profile_nid_update_marks_matching_document_verified(self):
        from unittest.mock import patch
        with patch(
            'accounts.views.verify_nid_document',
            return_value=(True, 'Document number verified successfully.'),
        ):
            response = self.client.patch('/api/v1/accounts/profile/', {
                'citizenship_number': '12-34-56-78901',
                'nid_document': self._make_fake_image(),
            }, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.nid_verified)
