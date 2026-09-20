import re
import io
import os
from pathlib import Path
try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None
from PIL import Image
from .models import AuditLog


def configure_tesseract():
    """Locate Tesseract on Windows when its installer has not refreshed PATH."""
    if pytesseract is None:
        return

    configured_path = os.environ.get('TESSERACT_CMD')
    candidates = [
        configured_path,
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


def log_audit(category, action, user=None, username=None, ip_address=None, status=AuditLog.Status.SUCCESS, metadata=None):
    actor_name = username
    if user and hasattr(user, 'username') and user.username:
        actor_name = user.username
    if not actor_name:
        actor_name = 'unauthenticated_client'

    actor_obj = user if (user and hasattr(user, 'is_authenticated') and user.is_authenticated) else None

    return AuditLog.objects.create(
        category=category,
        action=action,
        actor=actor_obj,
        actor_username=actor_name,
        ip_address=ip_address or '127.0.0.1',
        status=status,
        metadata=metadata
    )


def normalize_nid(s):
    """
    Normalize a National ID / Citizenship number for comparison.
    Strips surrounding whitespace, standardizes separators (converts / to -),
    collapses spaces around hyphens, then removes all remaining spaces so that:
        '12 - 34 - 56 - 78901'  ->  '12-34-56-78901'
        '12 / 34 / 56'          ->  '12-34-56'
        '12345678901'           ->  '12345678901'
    The canonical form keeps internal hyphens intact so that
    '12-34-56-78901' != '12345678901' (different numbers must not match).
    """
    if not s:
        return ''
    # Strip outer whitespace
    s = s.strip()
    # Standardize separators and collapse spaces around them: " / ", "- ", " -" -> "-"
    s = re.sub(r'\s*[-\/]\s*', '-', s)
    # Remove any remaining stray spaces
    s = s.replace(' ', '')
    # Lowercase for case-insensitive comparison (handles alphanumeric NID variants)
    return s.lower()


def extract_nid_candidates(text):
    """
    Extract candidate ID number strings from raw OCR text.
    Returns a list of raw matched strings (not yet normalized).
    Patterns target:
      - Nepali citizenship format: AA-BB-CC-DDDDD (with flexible separators)
      - Long numeric NID strings (7–16 digits)
    """
    if not text:
        return []

    patterns = [
        # Nepali citizenship: 1-4 digits, separator, 1-4 digits, separator, 1-4 digits, separator, 1-6 digits
        # Use negative lookbehinds and lookaheads to avoid matching partial strings from a longer NID
        r'(?<![\d\-\/])\d{1,4}\s*[-\/]\s*\d{1,4}\s*[-\/]\s*\d{1,4}\s*[-\/]\s*\d{1,6}(?![\d\-\/])',
        r'(?<![\d\-\/])\d{1,4}\s*[-\/]\s*\d{1,4}\s*[-\/]\s*\d{1,6}(?![\d\-\/])',
        # Plain long numeric NID (no hyphens)
        r'(?<![\d\-\/])\d{7,16}(?![\d\-\/])',
    ]

    found = []
    seen = set()
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            raw = m.group(0).strip()
            key = normalize_nid(raw)
            if key and key not in seen and len(key) >= 4:
                seen.add(key)
                found.append(raw)
    return found


def perform_ocr_on_image(image_file):
    """
    Run Tesseract OCR on a Django uploaded file (InMemoryUploadedFile or similar).
    Returns the raw extracted text string.

    Raises:
        pytesseract.pytesseract.TesseractNotFoundError  - if Tesseract binary absent.
        Exception  - for other read / processing failures.
    """
    if pytesseract is None:
        raise RuntimeError('The pytesseract package is not installed.')

    configure_tesseract()

    # Read image bytes into PIL
    image_file.seek(0)
    image_data = image_file.read()
    image = Image.open(io.BytesIO(image_data))

    # Convert to RGB if necessary (e.g., RGBA PNG)
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')

    # Use English (digits + letters) for fast, reliable extraction
    try:
        text = pytesseract.image_to_string(image, lang='eng')
        return text or ''
    finally:
        # Registration and profile updates save this same file after OCR.
        image_file.seek(0)


def verify_nid_document(citizenship_number, nid_document):
    """Return a safe OCR match result and a client-ready status message."""
    if not citizenship_number or not nid_document:
        return False, 'Enter the document number and upload its image to verify it.'

    try:
        ocr_text = perform_ocr_on_image(nid_document)
    except Exception:
        return False, 'OCR could not read the document. Please upload a clearer image and try again.'

    if not ocr_text or not ocr_text.strip():
        return False, 'OCR did not detect text in the document. Please upload a clearer, well-lit image.'

    entered_norm = normalize_nid(citizenship_number)
    matched = any(normalize_nid(candidate) == entered_norm for candidate in extract_nid_candidates(ocr_text))
    if matched:
        return True, 'Document number verified successfully.'
    return False, 'The entered number does not match the number detected on the uploaded document.'
