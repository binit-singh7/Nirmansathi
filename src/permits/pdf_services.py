import os
import io
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
import pypdf


ACADEMIC_DISCLAIMER_HEADER = "SIMULATED DOCUMENT — NIRMAN SATHI ACADEMIC PROJECT"
ACADEMIC_DISCLAIMER_SUB = (
    "This document is generated for academic demonstration purposes only "
    "and does not constitute an official government permit or certificate."
)

PRIMARY_COLOR = colors.HexColor('#0F2942')    # Deep Navy
SECONDARY_COLOR = colors.HexColor('#1E5F74')  # Blue-Teal
STAMP_BORDER_COLOR = colors.HexColor('#8B0000') # Deep Red / Maroon
STAMP_FILL_COLOR = colors.HexColor('#FFF5F5')
BORDER_COLOR = colors.HexColor('#CCCCCC')


class NumberedCanvas(canvas.Canvas):
    """Canvas that adds header disclaimer and footer with academic notices"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(colors.HexColor('#777777'))

        # Top academic banner
        self.drawCentredString(A4[0] / 2.0, A4[1] - 22, ACADEMIC_DISCLAIMER_HEADER)
        self.setFont("Helvetica", 6.5)
        self.drawCentredString(A4[0] / 2.0, A4[1] - 31, ACADEMIC_DISCLAIMER_SUB)

        # Top border line
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(36, A4[1] - 36, A4[0] - 36, A4[1] - 36)

        # Bottom footer line & disclaimer
        self.line(36, 40, A4[0] - 36, 40)
        self.setFont("Helvetica-Bold", 6.5)
        self.drawCentredString(A4[0] / 2.0, 28, f"{ACADEMIC_DISCLAIMER_HEADER} — Page {self._pageNumber} of {page_count}")
        self.setFont("Helvetica-Oblique", 6)
        self.drawCentredString(A4[0] / 2.0, 18, "For educational evaluation only • Not legally binding or officially recognized.")
        self.restoreState()


def get_municipality_office_title(municipality):
    """Dynamically determine the official municipal executive office name"""
    if not municipality:
        return "Office of the Municipal Executive"
    from locations.models import Municipality
    if municipality.type == Municipality.TypeChoices.RURAL_MUNICIPALITY:
        return "Office of the Rural Municipal Executive"
    return "Office of the Municipal Executive"


def draw_simulated_stamp_table(municipality_name, phase_name=None, is_completion=False):
    """Draws a table representing the generic simulated municipality stamp"""
    muni_text = (municipality_name or "MUNICIPALITY").upper()
    title_text = "CONSTRUCTION COMPLETED" if is_completion else f"{phase_name.upper()} APPROVED" if phase_name else "PHASE APPROVED"

    stamp_data = [
        [Paragraph(f"<font size=7 color='#8B0000'><b>NIRMANSATHI DEMO</b></font>", ParagraphStyle('C', alignment=1))],
        [Paragraph(f"<font size=8 color='#8B0000'><b>{muni_text}</b></font>", ParagraphStyle('C', alignment=1))],
        [Paragraph(f"<font size=7 color='#8B0000'><b>{title_text}</b></font>", ParagraphStyle('C', alignment=1))],
        [Paragraph(f"<font size=6 color='#B22222'><b>SIMULATED MUNICIPAL SEAL</b></font>", ParagraphStyle('C', alignment=1))],
    ]
    stamp_table = Table(stamp_data, colWidths=[180])
    stamp_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, STAMP_BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, STAMP_BORDER_COLOR),
        ('BACKGROUND', (0, 0), (-1, -1), STAMP_FILL_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    return stamp_table


def draw_simulated_signature_table(officer_name, approval_date):
    """Draws a simulated digital signature table with disclaimer"""
    date_str = approval_date.strftime('%Y-%m-%d') if approval_date else timezone.now().strftime('%Y-%m-%d')
    name = officer_name or "Authorized Municipal Officer"

    sig_data = [
        [Paragraph(f"<font size=8 color='#0F2942'><b>Approved By:</b> {name}</font>", ParagraphStyle('L'))],
        [Paragraph(f"<font size=8 color='#555555'><b>Designation:</b> Municipality Technical Officer</font>", ParagraphStyle('L'))],
        [Paragraph(f"<font size=8 color='#555555'><b>Date:</b> {date_str}</font>", ParagraphStyle('L'))],
        [Paragraph(f"<font size=10 color='#1E5F74'><i>~ {name} ~</i></font>", ParagraphStyle('L', alignment=1))],
        [Paragraph(f"<font size=6 color='#777777'><b>SAMPLE DIGITAL SIGNATURE</b> (Simulated)</font>", ParagraphStyle('L', alignment=1))],
    ]
    sig_table = Table(sig_data, colWidths=[200])
    sig_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return sig_table


def generate_permit_approval_letter_pdf(application, decision):
    """
    Generates a formal A4 Building Permit Approval Letter PDF when the officer approves
    the initial permit application. Includes municipal header, full application details,
    officer decision, simulated municipal stamp, and academic disclaimers.
    """
    municipality = application.municipality
    district = municipality.district if municipality else None
    province = district.province if district else None

    muni_name = municipality.name if municipality else "Municipality"
    office_name = get_municipality_office_title(municipality)
    dist_name = district.name if district else "District"
    prov_name = province.name if province else "Province"
    applicant_name = application.applicant.get_full_name() or application.applicant.username
    officer_name = decision.officer.get_full_name() or decision.officer.username
    approval_date = decision.decision_date or timezone.now()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=1,
        textColor=PRIMARY_COLOR
    )
    header_muni_style = ParagraphStyle(
        'HeaderMuni',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        alignment=1,
        textColor=PRIMARY_COLOR
    )
    header_sub_style = ParagraphStyle(
        'HeaderSub',
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=SECONDARY_COLOR
    )
    body_style = ParagraphStyle(
        'BodyDark',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#222222')
    )
    bold_style = ParagraphStyle(
        'BodyBold',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#111111')
    )

    elements = []

    # Municipal Header
    elements.append(Paragraph("<b>NIRMAN SATHI MUNICIPAL E-PERMIT SYSTEM</b>", header_sub_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"<b>{muni_name.upper()}</b>", header_muni_style))
    elements.append(Paragraph(f"{office_name}", header_sub_style))
    elements.append(Paragraph(f"{dist_name}, {prov_name}, Nepal", header_sub_style))
    elements.append(Spacer(1, 10))

    # Decorative Line
    dec_table = Table([['']], colWidths=[A4[0] - 72], rowHeights=[2])
    dec_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), SECONDARY_COLOR)]))
    elements.append(dec_table)
    elements.append(Spacer(1, 14))

    # Document Title
    elements.append(Paragraph("<b>BUILDING PERMIT APPROVAL LETTER</b>", title_style))
    elements.append(Paragraph(
        f"<font size=8 color='#666666'>Permit Reference No: {application.reference_number}</font>",
        ParagraphStyle('Sub', alignment=1)
    ))
    elements.append(Spacer(1, 14))

    # Approval Statement
    intro_text = (
        f"This is to certify that the Building Permit Application submitted by "
        f"<b>{applicant_name}</b> bearing Reference Number <b>{application.reference_number}</b> "
        f"has been duly reviewed and evaluated by the authorized Municipal Technical Officer of "
        f"<b>{muni_name}</b> in accordance with prevailing municipal building bylaws and "
        f"national construction safety standards. The application has been formally "
        f"<b><font color='#008000'>APPROVED</font></b> on {approval_date.strftime('%B %d, %Y')}."
    )
    elements.append(Paragraph(intro_text, body_style))
    elements.append(Spacer(1, 12))

    # Two-column details table
    col_w = (A4[0] - 72) / 2.0

    left_data = [
        [Paragraph("<b>Applicant & Property Details</b>", bold_style), ""],
        [Paragraph("<b>Applicant Name:</b>", body_style), Paragraph(applicant_name, body_style)],
        [Paragraph("<b>Municipality:</b>", body_style), Paragraph(muni_name, body_style)],
        [Paragraph("<b>District:</b>", body_style), Paragraph(dist_name, body_style)],
        [Paragraph("<b>Ward / Address:</b>", body_style), Paragraph(f"Ward {application.ward.ward_number}, {application.tole_address}", body_style)],
        [Paragraph("<b>Plot / Kitta No:</b>", body_style), Paragraph(application.plot_number, body_style)],
    ]
    right_data = [
        [Paragraph("<b>Building Specifications</b>", bold_style), ""],
        [Paragraph("<b>Application Type:</b>", body_style), Paragraph(application.get_application_type_display(), body_style)],
        [Paragraph("<b>Storeys Approved:</b>", body_style), Paragraph(str(application.storeys_count), bold_style)],
        [Paragraph("<b>Land Area:</b>", body_style), Paragraph(f"{application.land_area_sqft} sq ft", body_style)],
        [Paragraph("<b>Built-up Area:</b>", body_style), Paragraph(f"{application.total_built_up_area_sqft} sq ft", body_style)],
        [Paragraph("<b>Est. Cost (NPR):</b>", body_style), Paragraph(f"Rs. {float(application.estimated_cost):,.2f}", body_style)],
    ]

    t_left = Table(left_data, colWidths=[col_w * 0.45, col_w * 0.55])
    t_left.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EFF6FF')),
        ('SPAN', (0, 0), (1, 0)),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))

    t_right = Table(right_data, colWidths=[col_w * 0.45, col_w * 0.55])
    t_right.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EFF6FF')),
        ('SPAN', (0, 0), (1, 0)),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))

    details_grid = Table([[t_left, t_right]], colWidths=[col_w, col_w])
    details_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(details_grid)
    elements.append(Spacer(1, 12))

    # Approval Decision & Conditions
    remarks_text = decision.remarks or (
        "The building design and structural plans have been found to comply with municipal building "
        "regulations including setback requirements, height restrictions, and safety standards."
    )
    conditions_data = [
        [Paragraph("<b>Officer Decision Remarks & Approval Conditions:</b>", bold_style)],
        [Paragraph(remarks_text, body_style)],
        [Paragraph(
            "<i>Authorization: The applicant is hereby authorized to commence building construction "
            "in accordance with the approved architectural drawings. Construction must proceed under "
            "municipal construction phase monitoring and inspection protocol.</i>",
            ParagraphStyle('Note', fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#444444'))
        )],
    ]
    conditions_table = Table(conditions_data, colWidths=[A4[0] - 72])
    conditions_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F0FDF4')),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#16A34A')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(conditions_table)
    elements.append(Spacer(1, 18))

    # Signature & Stamp
    stamp_tbl = draw_simulated_stamp_table(muni_name, "PERMIT APPROVED")
    sig_tbl = draw_simulated_signature_table(officer_name, approval_date)

    auth_table = Table([[stamp_tbl, sig_tbl]], colWidths=[(A4[0] - 72) / 2.0, (A4[0] - 72) / 2.0])
    auth_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(auth_table)

    # Build PDF
    doc.build(elements, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Save to application
    filename = f"Permit_Approval_Letter_{application.reference_number}.pdf"
    application.permit_approval_letter_pdf.save(filename, ContentFile(pdf_bytes), save=True)
    return application.permit_approval_letter_pdf.url


def generate_phase_approval_pdf(phase):
    """

    Generates a formal A4 Construction Phase Approval PDF for an approved phase.
    Dynamically fetches municipality, district, province, applicant, and building details.
    Includes simulated municipality stamp, sample signature, and academic disclaimers.
    """
    app = phase.application
    municipality = app.municipality
    district = municipality.district if municipality else None
    province = district.province if district else None

    muni_name = municipality.name if municipality else "Municipality"
    office_name = get_municipality_office_title(municipality)
    dist_name = district.name if district else "District"
    prov_name = province.name if province else "Province"
    applicant_name = app.applicant.get_full_name() or app.applicant.username
    officer_name = phase.reviewed_by.get_full_name() or phase.reviewed_by.username if phase.reviewed_by else "Municipal Officer"
    approval_date = phase.approved_at or timezone.now()
    submission_date = phase.submitted_at or app.created_at

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=1,
        textColor=PRIMARY_COLOR
    )
    header_muni_style = ParagraphStyle(
        'HeaderMuni',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        alignment=1,
        textColor=PRIMARY_COLOR
    )
    header_sub_style = ParagraphStyle(
        'HeaderSub',
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=SECONDARY_COLOR
    )
    body_style = ParagraphStyle(
        'BodyDark',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#222222')
    )
    bold_style = ParagraphStyle(
        'BodyBold',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#111111')
    )

    elements = []

    # Municipal Header
    elements.append(Paragraph(f"<b>NIRMANSATHI MUNICIPAL E-PERMIT SYSTEM</b>", header_sub_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"<b>{muni_name.upper()}</b>", header_muni_style))
    elements.append(Paragraph(f"{office_name}", header_sub_style))
    elements.append(Paragraph(f"{dist_name}, {prov_name}, Nepal", header_sub_style))
    elements.append(Spacer(1, 10))

    # Decorative Line
    dec_table = Table([['']], colWidths=[A4[0] - 72], rowHeights=[2])
    dec_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), SECONDARY_COLOR)]))
    elements.append(dec_table)
    elements.append(Spacer(1, 12))

    # Document Title
    phase_title = f"{phase.name.upper()} APPROVAL"
    elements.append(Paragraph(f"<b>{phase_title}</b>", title_style))
    elements.append(Paragraph(f"<font size=8 color='#666666'>Phase Monitoring Reference: {app.reference_number}-P{phase.sequence}</font>", ParagraphStyle('Sub', alignment=1)))
    elements.append(Spacer(1, 12))

    # Overview text
    intro_text = (
        f"This official approval certifies that technical site inspection and document review "
        f"for <b>{phase.name}</b> under Building Permit <b>{app.reference_number}</b> have been completed "
        f"and meet municipal construction safety and planning regulations."
    )
    elements.append(Paragraph(intro_text, body_style))
    elements.append(Spacer(1, 10))

    # Two-Column Table: Permit & Property Details | Phase Inspection Details
    col_w = (A4[0] - 72) / 2.0
    left_data = [
        [Paragraph("<b>Property & Permit Details</b>", bold_style), ""],
        [Paragraph("<b>Permit / Ref No:</b>", body_style), Paragraph(app.reference_number, bold_style)],
        [Paragraph("<b>Applicant Name:</b>", body_style), Paragraph(applicant_name, body_style)],
        [Paragraph("<b>Municipality:</b>", body_style), Paragraph(muni_name, body_style)],
        [Paragraph("<b>Ward / Address:</b>", body_style), Paragraph(f"Ward {app.ward.ward_number}, {app.tole_address}", body_style)],
        [Paragraph("<b>Plot / Kitta No:</b>", body_style), Paragraph(app.plot_number, body_style)],
        [Paragraph("<b>Storeys Approved:</b>", body_style), Paragraph(str(app.storeys_count), body_style)],
        [Paragraph("<b>Built-up Area:</b>", body_style), Paragraph(f"{app.total_built_up_area_sqft} sq ft", body_style)],
    ]
    right_data = [
        [Paragraph("<b>Phase Technical Assessment</b>", bold_style), ""],
        [Paragraph("<b>Phase Name:</b>", body_style), Paragraph(phase.name, bold_style)],
        [Paragraph("<b>Phase Sequence:</b>", body_style), Paragraph(f"Phase {phase.sequence}", body_style)],
        [Paragraph("<b>Approval Status:</b>", body_style), Paragraph(f"<font color='#008000'><b>{phase.status}</b></font>", bold_style)],
        [Paragraph("<b>Submitted Date:</b>", body_style), Paragraph(submission_date.strftime('%Y-%m-%d'), body_style)],
        [Paragraph("<b>Approval Date:</b>", body_style), Paragraph(approval_date.strftime('%Y-%m-%d'), body_style)],
        [Paragraph("<b>Inspected By:</b>", body_style), Paragraph(officer_name, body_style)],
        [Paragraph("<b>Designation:</b>", body_style), Paragraph("Municipality Officer", body_style)],
    ]

    t_left = Table(left_data, colWidths=[col_w * 0.45, col_w * 0.55])
    t_left.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('SPAN', (0, 0), (1, 0)),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    t_right = Table(right_data, colWidths=[col_w * 0.45, col_w * 0.55])
    t_right.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F1F5F9')),
        ('SPAN', (0, 0), (1, 0)),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    details_grid = Table([[t_left, t_right]], colWidths=[col_w, col_w])
    details_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(details_grid)
    elements.append(Spacer(1, 12))

    # Officer Remarks
    remarks_text = phase.review_notes or "Technical inspection completed. Work verified in accordance with approved architectural drawings and setbacks."
    remarks_data = [
        [Paragraph("<b>Officer Technical Inspection Remarks & Directives:</b>", bold_style)],
        [Paragraph(remarks_text, body_style)],
        [Paragraph("<i>Note: Authorization to proceed to the next construction phase is hereby granted.</i>", ParagraphStyle('Note', fontName='Helvetica-Oblique', fontSize=8, textColor=colors.HexColor('#444444')))]
    ]
    remarks_table = Table(remarks_data, colWidths=[A4[0] - 72])
    remarks_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(remarks_table)
    elements.append(Spacer(1, 16))

    # Signatures & Stamps row
    stamp_tbl = draw_simulated_stamp_table(muni_name, phase.name)
    sig_tbl = draw_simulated_signature_table(officer_name, approval_date)

    auth_table = Table([[stamp_tbl, sig_tbl]], colWidths=[(A4[0] - 72) / 2.0, (A4[0] - 72) / 2.0])
    auth_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(auth_table)

    # Build PDF
    doc.build(elements, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Save to file
    filename = f"Phase_Approval_{app.reference_number}_{phase.sequence}.pdf"
    phase.generated_approval_pdf.save(filename, ContentFile(pdf_bytes), save=True)
    return phase.generated_approval_pdf.url


def generate_completion_certificate_pdf(application):
    """
    Generates the formal A4 Building Construction Completion Certificate.
    Includes dynamic municipality header, full application details, phase history table,
    academic completion statement, simulated municipality stamp, and simulated signature.
    """
    municipality = application.municipality
    district = municipality.district if municipality else None
    province = district.province if district else None

    muni_name = municipality.name if municipality else "Municipality"
    office_name = get_municipality_office_title(municipality)
    dist_name = district.name if district else "District"
    prov_name = province.name if province else "Province"
    applicant_name = application.applicant.get_full_name() or application.applicant.username
    officer_name = application.completion_reviewed_by.get_full_name() or application.completion_reviewed_by.username if application.completion_reviewed_by else "Chief Technical Officer"
    completion_date = application.completed_at or timezone.now()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()
    cert_title_style = ParagraphStyle(
        'CertTitle',
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=1,
        textColor=PRIMARY_COLOR
    )
    header_muni_style = ParagraphStyle(
        'HeaderMuni',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        alignment=1,
        textColor=PRIMARY_COLOR
    )
    header_sub_style = ParagraphStyle(
        'HeaderSub',
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=SECONDARY_COLOR
    )
    body_style = ParagraphStyle(
        'BodyDark',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#222222')
    )
    bold_style = ParagraphStyle(
        'BodyBold',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#111111')
    )

    elements = []

    # Municipal Header
    elements.append(Paragraph(f"<b>NIRMANSATHI DIGITAL MUNICIPAL GOVERNANCE</b>", header_sub_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"<b>{muni_name.upper()}</b>", header_muni_style))
    elements.append(Paragraph(f"{office_name}", header_sub_style))
    elements.append(Paragraph(f"{dist_name}, {prov_name}, Nepal", header_sub_style))
    elements.append(Spacer(1, 8))

    # Decorative Line
    dec_table = Table([['']], colWidths=[A4[0] - 72], rowHeights=[2])
    dec_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), SECONDARY_COLOR)]))
    elements.append(dec_table)
    elements.append(Spacer(1, 10))

    # Certificate Title
    elements.append(Paragraph("<b>BUILDING CONSTRUCTION COMPLETION CERTIFICATE</b>", cert_title_style))
    elements.append(Paragraph(f"<font size=8 color='#666666'>Certificate Ref: NS-CCC-{application.reference_number}</font>", ParagraphStyle('Sub', alignment=1)))
    elements.append(Spacer(1, 10))

    # Formal Academic Completion Statement
    statement = (
        "<b>CERTIFICATE OF COMPLETION RECORD</b><br/>"
        "This certificate records that the construction project associated with the building permit referenced below "
        "has been marked as completed following the recorded construction phase approvals and final review in the "
        "NirmanSathi system. All required structural phases and mandatory inspections have been documented and certified."
    )
    stmt_table = Table([[Paragraph(statement, body_style)]], colWidths=[A4[0] - 72])
    stmt_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 1, SECONDARY_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(stmt_table)
    elements.append(Spacer(1, 10))

    # Building & Owner Specifications Table
    prop_w = (A4[0] - 72) / 4.0
    spec_data = [
        [
            Paragraph("<b>Permit No:</b>", bold_style), Paragraph(application.reference_number, body_style),
            Paragraph("<b>Applicant Name:</b>", bold_style), Paragraph(applicant_name, body_style)
        ],
        [
            Paragraph("<b>Municipality:</b>", bold_style), Paragraph(muni_name, body_style),
            Paragraph("<b>Ward / Address:</b>", bold_style), Paragraph(f"Ward {application.ward.ward_number}, {application.tole_address}", body_style)
        ],
        [
            Paragraph("<b>Plot / Kitta:</b>", bold_style), Paragraph(application.plot_number, body_style),
            Paragraph("<b>Storeys:</b>", bold_style), Paragraph(f"{application.storeys_count} Storeys", body_style)
        ],
        [
            Paragraph("<b>Built-up Area:</b>", bold_style), Paragraph(f"{application.total_built_up_area_sqft} sq ft", body_style),
            Paragraph("<b>Completion Date:</b>", bold_style), Paragraph(completion_date.strftime('%Y-%m-%d'), body_style)
        ],
    ]
    spec_table = Table(spec_data, colWidths=[prop_w * 0.9, prop_w * 1.1, prop_w * 0.9, prop_w * 1.1])
    spec_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F1F5F9')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F1F5F9')),
    ]))
    elements.append(spec_table)
    elements.append(Spacer(1, 10))

    # Construction Phase History Table
    elements.append(Paragraph("<b>Verified Construction Phase History:</b>", bold_style))
    elements.append(Spacer(1, 4))

    history_headers = [
        Paragraph("<b>Phase</b>", bold_style),
        Paragraph("<b>Stage</b>", bold_style),
        Paragraph("<b>Status</b>", bold_style),
        Paragraph("<b>Approved Date</b>", bold_style),
        Paragraph("<b>Inspected By</b>", bold_style)
    ]
    history_data = [history_headers]

    phases = application.construction_phases.all()
    for p in phases:
        status_color = '#008000' if p.status == 'APPROVED' else '#666666'
        history_data.append([
            Paragraph(p.name, body_style),
            Paragraph(f"Phase {p.sequence}", body_style),
            Paragraph(f"<font color='{status_color}'><b>{p.status}</b></font>", body_style),
            Paragraph(p.approved_at.strftime('%Y-%m-%d') if p.approved_at else 'Pending', body_style),
            Paragraph(p.reviewed_by.get_full_name() or p.reviewed_by.username if p.reviewed_by else 'Municipal Inspector', body_style),
        ])

    table_w = (A4[0] - 72)
    history_table = Table(
        history_data,
        colWidths=[table_w * 0.30, table_w * 0.15, table_w * 0.18, table_w * 0.17, table_w * 0.20]
    )
    history_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(history_table)
    elements.append(Spacer(1, 12))

    # Final Remarks
    final_remarks = application.completion_remarks or "All phases completed in conformity with municipal building bylaws. Final inspection confirmed."
    rem_table = Table([[
        Paragraph(f"<b>Final Technical Assessment:</b> {final_remarks}", body_style)
    ]], colWidths=[A4[0] - 72])
    rem_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(rem_table)
    elements.append(Spacer(1, 14))

    # Stamp and Signature
    stamp_tbl = draw_simulated_stamp_table(muni_name, is_completion=True)
    sig_tbl = draw_simulated_signature_table(officer_name, completion_date)

    auth_table = Table([[stamp_tbl, sig_tbl]], colWidths=[(A4[0] - 72) / 2.0, (A4[0] - 72) / 2.0])
    auth_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(auth_table)

    # Build PDF
    doc.build(elements, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"Completion_Certificate_{application.reference_number}.pdf"
    application.completion_certificate_pdf.save(filename, ContentFile(pdf_bytes), save=True)
    return application.completion_certificate_pdf.url


def stamp_phase_blueprint(phase):
    """
    Non-destructively stamps the primary architectural blueprint associated with this phase.
    If no blueprint is uploaded under phase documents, checks the parent permit application documents.
    Preserves original uploaded files completely unchanged.
    Preserves all pages, dimensions, and orientations for multi-page PDFs.
    Saves the stamped approved copy separately under media/generated_documents/stamped_blueprints/.
    """
    from .models import ConstructionPhaseDocument, ApplicationDocument

    # 1. Locate blueprint document
    blueprint_doc = phase.documents.filter(
        document_type=ConstructionPhaseDocument.DocumentType.BLUEPRINT
    ).first()

    if not blueprint_doc:
        # Fall back to parent application's blueprint if not uploaded separately for phase
        blueprint_doc = phase.application.documents.filter(
            document_type=ApplicationDocument.DocumentType.BLUEPRINT
        ).first()

    if not blueprint_doc or not blueprint_doc.file:
        raise ValidationError({"error": "No architectural blueprint has been submitted for this phase."})

    orig_file_path = blueprint_doc.file.path
    if not os.path.exists(orig_file_path):
        raise ValidationError({"error": f"Original blueprint file not found on disk at {orig_file_path}"})

    app = phase.application
    muni_name = app.municipality.name if app.municipality else "Municipality"
    officer_name = phase.reviewed_by.get_full_name() or phase.reviewed_by.username if phase.reviewed_by else "Municipal Officer"
    approval_date_str = (phase.approved_at or timezone.now()).strftime('%Y-%m-%d')
    phase_label = phase.name.upper()
    permit_ref = app.reference_number

    ext = os.path.splitext(orig_file_path)[1].lower()

    if ext == '.pdf':
        # --- PDF Blueprint Stamping (Multi-page safe) ---
        reader = pypdf.PdfReader(orig_file_path)
        writer = pypdf.PdfWriter()

        stamp_w, stamp_h = 250, 95

        for page in reader.pages:
            p_width = float(page.mediabox.width)
            p_height = float(page.mediabox.height)

            # Create an in-memory ReportLab overlay PDF of exact same dimensions
            stamp_buf = io.BytesIO()
            stamp_canvas = canvas.Canvas(stamp_buf, pagesize=(p_width, p_height))

            # Bottom-right corner placement (title-block area)
            pos_x = p_width - stamp_w - 20
            pos_y = 20

            # Stamp box background and border
            stamp_canvas.saveState()
            stamp_canvas.setFillColor(colors.HexColor('#FFF5F5'))
            stamp_canvas.setStrokeColor(STAMP_BORDER_COLOR)
            stamp_canvas.setLineWidth(1.5)
            stamp_canvas.roundRect(pos_x, pos_y, stamp_w, stamp_h, 4, fill=1, stroke=1)

            # Inner frame
            stamp_canvas.setStrokeColor(STAMP_BORDER_COLOR)
            stamp_canvas.setLineWidth(0.5)
            stamp_canvas.roundRect(pos_x + 3, pos_y + 3, stamp_w - 6, stamp_h - 6, 2, fill=0, stroke=1)

            # Stamp text
            stamp_canvas.setFillColor(STAMP_BORDER_COLOR)
            stamp_canvas.setFont("Helvetica-Bold", 8)
            stamp_canvas.drawCentredString(pos_x + stamp_w / 2.0, pos_y + stamp_h - 13, "NIRMANSATHI DEMO")

            stamp_canvas.setFont("Helvetica-Bold", 7.5)
            stamp_canvas.drawCentredString(pos_x + stamp_w / 2.0, pos_y + stamp_h - 23, muni_name.upper())

            stamp_canvas.setFont("Helvetica-Bold", 7)
            stamp_canvas.drawCentredString(pos_x + stamp_w / 2.0, pos_y + stamp_h - 33, f"CONSTRUCTION PHASE APPROVED: {phase_label}")

            stamp_canvas.setFont("Helvetica", 6.5)
            stamp_canvas.setFillColor(PRIMARY_COLOR)
            stamp_canvas.drawString(pos_x + 10, pos_y + stamp_h - 45, f"Permit No: {permit_ref}")
            stamp_canvas.drawString(pos_x + 10, pos_y + stamp_h - 55, f"Approved Date: {approval_date_str}")
            stamp_canvas.drawString(pos_x + 10, pos_y + stamp_h - 65, f"Officer: {officer_name}")

            # Simulated stamp & signature notice
            stamp_canvas.setFont("Helvetica-Oblique", 6)
            stamp_canvas.setFillColor(colors.HexColor('#777777'))
            stamp_canvas.drawCentredString(pos_x + stamp_w / 2.0, pos_y + 15, "SIMULATED STAMP & SIGNATURE")
            stamp_canvas.setFont("Helvetica-Bold", 5.5)
            stamp_canvas.drawCentredString(pos_x + stamp_w / 2.0, pos_y + 6, "SIMULATED DOCUMENT — ACADEMIC PROJECT")

            stamp_canvas.restoreState()
            stamp_canvas.showPage()
            stamp_canvas.save()

            stamp_buf.seek(0)
            overlay_reader = pypdf.PdfReader(stamp_buf)
            page.merge_page(overlay_reader.pages[0])
            writer.add_page(page)

        out_buf = io.BytesIO()
        writer.write(out_buf)
        out_bytes = out_buf.getvalue()

        out_filename = f"Stamped_Blueprint_{permit_ref}_Phase_{phase.sequence}.pdf"
        phase.generated_stamped_blueprint.save(out_filename, ContentFile(out_bytes), save=True)
        return phase.generated_stamped_blueprint.url

    elif ext in ['.png', '.jpg', '.jpeg']:
        # --- Image Blueprint Stamping (Pillow) ---
        img = Image.open(orig_file_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        w, h = img.size

        stamp_w, stamp_h = 420, 150
        pos_x = w - stamp_w - 30
        pos_y = h - stamp_h - 30

        # Draw stamp rectangle
        draw.rectangle([pos_x, pos_y, pos_x + stamp_w, pos_y + stamp_h], fill="#FFF5F5", outline="#8B0000", width=3)
        draw.rectangle([pos_x + 5, pos_y + 5, pos_x + stamp_w - 5, pos_y + stamp_h - 5], outline="#8B0000", width=1)

        # Draw lines of text
        lines = [
            "NIRMANSATHI DEMO",
            muni_name.upper(),
            f"PHASE APPROVED: {phase_label}",
            f"Permit: {permit_ref} | Approved: {approval_date_str}",
            f"Officer: {officer_name}",
            "SIMULATED STAMP & SIGNATURE — ACADEMIC PROJECT"
        ]

        curr_y = pos_y + 12
        for line in lines:
            draw.text((pos_x + 15, curr_y), line, fill="#8B0000")
            curr_y += 21

        out_buf = io.BytesIO()
        img.save(out_buf, format='JPEG', quality=95)
        out_bytes = out_buf.getvalue()

        out_filename = f"Stamped_Blueprint_{permit_ref}_Phase_{phase.sequence}.jpg"
        phase.generated_stamped_blueprint.save(out_filename, ContentFile(out_bytes), save=True)
        return phase.generated_stamped_blueprint.url

    else:
        raise ValidationError({"error": f"Unsupported blueprint file format '{ext}'. Must be PDF, PNG, or JPG."})
