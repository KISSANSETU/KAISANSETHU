import os
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

CERTIFICATE_DIR = os.path.join(
    BASE_DIR,
    "certificates"
)

os.makedirs(
    CERTIFICATE_DIR,
    exist_ok=True
)


def generate_quality_certificate(
    certificate_number,
    farmer_name,
    crop,
    grade,
    confidence,
    latitude,
    longitude,
    location_source,
    image_hash,
    model_name
):

    filename = (
        f"{certificate_number}.pdf"
    )

    path = os.path.join(
        CERTIFICATE_DIR,
        filename
    )

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "GRAM AI",
            styles["Title"]
        )
    )

    story.append(
        Paragraph(
            "Produce Quality & Geolocation Certificate",
            styles["Heading2"]
        )
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    issued_at = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    data = [
        ["Certificate Number", certificate_number],
        ["Farmer", farmer_name],
        ["Crop", crop],
        ["Automatic Grade", f"Grade {grade}"],
        ["YOLO Confidence", f"{confidence * 100:.2f}%"],
        ["Latitude", f"{latitude:.6f}"],
        ["Longitude", f"{longitude:.6f}"],
        ["Location Source", location_source.upper()],
        ["YOLO Model", model_name],
        ["Issued At", issued_at],
        ["Image SHA-256", image_hash]
    ]

    table = Table(
        data,
        colWidths=[
            55 * mm,
            110 * mm
        ]
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EAF4ED")
            ),
            (
                "FONTNAME",
                (0, 0),
                (0, -1),
                "Helvetica-Bold"
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "PADDING",
                (0, 0),
                (-1, -1),
                8
            )
        ])
    )

    story.append(
        table
    )

    story.append(
        Spacer(
            1,
            8 * mm
        )
    )

    story.append(
        Paragraph(
            "This certificate records the automatic GRAM AI "
            "quality classification and the location linked "
            "to the produce image during inspection.",
            styles["BodyText"]
        )
    )

    doc.build(
        story
    )

    return path