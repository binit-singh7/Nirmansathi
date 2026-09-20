"""
accounts/ocr_views.py

Backend-only NID / Citizenship document OCR verification endpoint.

POST /api/v1/accounts/nid/verify/
  - Requires authentication.
  - Accepts multipart: citizenship_number (str) + nid_document (image).
  - Runs server-side Tesseract OCR on the uploaded image.
  - Compares the entered number against extracted candidates (normalized).
  - Returns {"matched": true/false, "message": "..."}.
  - NEVER returns OCR raw text or candidate numbers to the client.
  - If OCR fails for any reason → matched: false (fail-closed, per spec).
"""

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import permissions, status

from .utils import verify_nid_document


class NIDVerifyView(APIView):
    """
    Verify a user-submitted NID/Citizenship number against a scanned document image.

    The backend is the sole source of truth.  The client receives only a boolean
    match result — never the OCR text or any extracted candidate strings.
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        citizenship_number = request.data.get('citizenship_number', '').strip()
        nid_document = request.FILES.get('nid_document')

        # --- Input validation ---
        if not citizenship_number:
            return Response(
                {'detail': 'citizenship_number is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not nid_document:
            return Response(
                {'detail': 'nid_document (image file) is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        matched, message = verify_nid_document(citizenship_number, nid_document)
        return Response({'matched': matched, 'message': message}, status=status.HTTP_200_OK)
