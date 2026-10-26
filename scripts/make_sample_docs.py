"""Generate the sample PDF and DOCX in data/sample_docs/ using only the standard library.

Run once (the outputs are committed):

    python scripts/make_sample_docs.py

Why hand-written? A DOCX is a zip of XML files and a simple PDF is a short text format, so no
extra package is needed. Output is byte-for-byte deterministic (fixed zip timestamps), so the
files' SHA-256 fingerprints never change between runs.
"""

import zipfile
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_docs"
NOTICE = "Lumen Home is a fictional company. Sample data for the MultiSource RAG Chatbot."

# ---------------------------------------------------------------------------- PDF content
# Two pages of troubleshooting text; each inner list is one page, one string per line.
PDF_PAGES = [
    [
        "Orbit T2 Troubleshooting Guide",
        NOTICE,
        "",
        "Error codes",
        "E-114  Low power. The thermostat is not getting continuous power.",
        "       Install the C-wire adapter or connect a C-wire. Random reboots are a sign.",
        "E-207  Wi-Fi connection failed. Check the password and that the router is on.",
        "       Move the router closer or use the 2.4 GHz band, which reaches further.",
        "E-310  Temperature sensor fault. Restart the thermostat from Settings > Restart.",
        "       If the error returns within a day, contact Lumen Home support.",
        "E-402  No heating detected. The system did not heat within 15 minutes.",
        "       Check the furnace switch, the breaker and the W1 wire.",
        "E-405  No cooling detected. The system did not cool within 15 minutes.",
        "       Check the outdoor unit breaker and the Y1 wire.",
    ],
    [
        "Common problems",
        "",
        "The display is blank: check the breaker, then make sure the display is clipped",
        "firmly onto the base plate. Wait two minutes after power returns.",
        "",
        "The room feels warmer than the setting: the thermostat may be in direct sunlight",
        "or above a lamp. Move it, or add a wireless room sensor and set it as primary.",
        "",
        "The schedule is ignored: check that Hold is not active. A manual change holds",
        "until the next schedule step unless you choose Hold permanently.",
        "",
        "Contacting support",
        "Have your serial number ready. It is in Settings > About and on the box.",
        "Support hours are 8 a.m. to 8 p.m., Monday to Saturday.",
    ],
]

# --------------------------------------------------------------------------- DOCX content
# (style, text) pairs. Styles map to headings when converted to Markdown.
DOCX_PARAGRAPHS = [
    ("Title", "Lumen Home Warranty and Returns Policy"),
    ("Normal", NOTICE),
    ("Heading1", "Limited warranty"),
    (
        "Normal",
        "The Orbit T2 is covered by a two-year limited warranty from the date of purchase. "
        "The warranty covers defects in materials and workmanship under normal use. It does "
        "not cover damage from incorrect wiring, line-voltage connections, water or "
        "unauthorised repairs.",
    ),
    ("Heading2", "How to make a warranty claim"),
    (
        "Normal",
        "Contact Lumen Home support with your serial number and proof of purchase. Support "
        "may ask for photos of the wiring. If the claim is approved, we send a replacement "
        "unit before you return the faulty one, so your home is never without heating.",
    ),
    ("Heading1", "Returns"),
    (
        "Normal",
        "You can return an Orbit T2 bought directly from Lumen Home within 30 days for a full "
        "refund. The thermostat must be complete with all accessories. Return shipping is "
        "free. Refunds are paid to the original payment method within 10 business days of "
        "receiving the return.",
    ),
    ("Heading2", "Items that cannot be returned"),
    (
        "Normal",
        "Gift cards, installation services that were already completed, and thermostats "
        "bought from other retailers cannot be returned to Lumen Home. Retailer purchases "
        "follow the retailer's own return policy.",
    ),
]


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(pages: list[list[str]]) -> bytes:
    """Build a minimal multi-page PDF with Helvetica text."""
    objects: list[bytes] = []
    page_count = len(pages)
    font_id = 3 + 2 * page_count  # after catalog, pages, and (page, content) pairs
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    for i, lines in enumerate(pages):
        content_id = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        ops = ["BT", "/F1 11 Tf", "14 TL", "60 740 Td"]
        ops += [f"({_pdf_escape(line)}) Tj T*" for line in lines]
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
    out += f"startxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
STYLES = {"Title": "Title", "Heading1": "heading 1", "Heading2": "heading 2"}


def build_docx(paragraphs: list[tuple[str, str]]) -> bytes:
    """Build a minimal Word document whose heading styles convert to Markdown headings."""
    body = "".join(
        "<w:p>"
        + (f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style != "Normal" else "")
        + f'<w:r><w:t xml:space="preserve">{_xml_escape(text)}</w:t></w:r></w:p>'
        for style, text in paragraphs
    )
    styles = "".join(
        f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/></w:style>'
        for sid, name in STYLES.items()
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>"
        ),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f"<w:document {W_NS}><w:body>{body}</w:body></w:document>"
        ),
        "word/styles.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f"<w:styles {W_NS}>{styles}</w:styles>"
        ),
    }
    path = OUT_DIR / ".tmp.docx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))  # fixed => deterministic
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED)
    data = path.read_bytes()
    path.unlink()
    return data


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "orbit_troubleshooting.pdf").write_bytes(build_pdf(PDF_PAGES))
    (OUT_DIR / "lumen_warranty_returns.docx").write_bytes(build_docx(DOCX_PARAGRAPHS))
    print(f"wrote sample PDF and DOCX to {OUT_DIR}")


if __name__ == "__main__":
    main()
