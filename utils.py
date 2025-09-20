from typing import Optional, Tuple, List
from PIL import Image
import os
from datetime import datetime
import pytz
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Image as RLImage, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import pandas as pd
import io

IST = pytz.timezone('Asia/Kolkata')


def now_ist() -> datetime:
    return datetime.now(IST)


def to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return IST.localize(dt)
    return dt.astimezone(IST)


def fmt_ts(dt: datetime) -> str:
    return to_ist(dt).strftime('%Y-%m-%d %H:%M:%S')


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def save_image_for_employee(employee_id: int, image_bytes: bytes, timestamp: Optional[datetime] = None) -> Tuple[str, str]:
    ts = timestamp or now_ist()
    year = ts.strftime('%Y')
    month = ts.strftime('%m')
    day = ts.strftime('%d')
    base_dir = os.path.join('photos', str(employee_id), year, month, day)
    ensure_dir(base_dir)
    filename = ts.strftime('%H%M%S') + '.jpg'
    full_path = os.path.join(base_dir, filename)
    thumb_path = os.path.join(base_dir, ts.strftime('%H%M%S') + '_thumb.jpg')
    # Compress and resize
    with Image.open(io.BytesIO(image_bytes)) as img:
        img = img.convert('RGB')
        # Resize preserving aspect ratio to max width 800px
        max_w = 800
        if img.width > max_w:
            ratio = max_w / float(img.width)
            new_size = (max_w, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        img.save(full_path, format='JPEG', quality=75, optimize=True)
        # Thumbnail
        thumb = img.copy()
        thumb.thumbnail((240, 240))
        thumb.save(thumb_path, format='JPEG', quality=70, optimize=True)
    return full_path, thumb_path


# PDF/CSV EXPORT ---------------------------------------------------------

def export_csv(df: pd.DataFrame, path: str) -> str:
    df.to_csv(path, index=False)
    return path


def export_pdf_attendance(path: str, title: str, table_data: List[List[str]], thumbnails: Optional[List[str]] = None) -> str:
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 12))

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(table)

    if thumbnails:
        elements.append(Spacer(1, 24))
        elements.append(Paragraph('Thumbnails', styles['Heading2']))
        elements.append(Spacer(1, 12))
        # add thumbnails in rows
        row_imgs = []
        max_per_row = 3
        for i, t in enumerate(thumbnails):
            if os.path.exists(t):
                try:
                    row_imgs.append(RLImage(t, width=1.8*inch, height=1.8*inch))
                except Exception:
                    pass
            if (i+1) % max_per_row == 0 and row_imgs:
                elements.append(Table([row_imgs]))
                row_imgs = []
        if row_imgs:
            elements.append(Table([row_imgs]))

    doc.build(elements)
    return path


# GEO -------------------------------------------------------------------
def reverse_geocode(lat: Optional[float], lng: Optional[float]) -> Optional[str]:
    """Resolve a human-readable place from coordinates via Nominatim.
    Returns a short display name or None on failure.
    """
    if lat is None or lng is None:
        return None
    try:
        url = 'https://nominatim.openstreetmap.org/reverse'
        params = {
            'format': 'jsonv2',
            'lat': lat,
            'lon': lng,
            'zoom': 16,
            'addressdetails': 1,
        }
        headers = {
            'User-Agent': 'AttendanceApp/1.0 (Contact: admin@example.com)'
        }
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('display_name') or None
    except Exception:
        pass
    return None
