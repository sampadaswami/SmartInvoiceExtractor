"""
SMART INVOICE EXTRACTOR – AUTO COLUMN VERSION
Run: streamlit run smart_invoice_extractor.py
"""

import os
import re
import tempfile
import io
from datetime import datetime

import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageEnhance
import fitz  # PyMuPDF
from pdf2image import convert_from_path

# ==============================
# CONFIG
# ==============================
pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"  # Streamlit Cloud safe
SUPPORTED_EXT = [".pdf", ".png", ".jpg", ".jpeg"]

# ==============================
# OCR FUNCTIONS
# ==============================
def extract_text_from_image(path):
    img = Image.open(path).convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.0)
    return pytesseract.image_to_string(img, lang="eng")


def extract_text_from_pdf(path):
    text = ""
    doc = fitz.open(path)
    for page in doc:
        text += page.get_text()
    doc.close()

    # OCR fallback if PDF text is weak
    if len(text.strip()) < 100:
        for img in convert_from_path(path):
            text += pytesseract.image_to_string(img, lang="eng")

    return text


# ==============================
# AUTO FIELD EXTRACTION
# ==============================
def auto_extract_fields(text):
    data = {}
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 2]

    # Generic KEY : VALUE
    for line in lines:
        m = re.match(r"([A-Za-z\s\.\-%/]+)\s*[:\-]\s*(.+)", line)
        if m:
            key = m.group(1).strip().title()
            value = m.group(2).strip()
            if len(key) < 40 and len(value) < 120:
                data[key] = value

    # Invoice Number
    m = re.search(r"Invoice\s*No\.?\s*[:\-]?\s*([A-Z0-9\/\-]+)", text, re.I)
    if m:
        data["Invoice No"] = m.group(1)

    # Invoice Date
    m = re.search(
        r"Invoice\s*Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        text,
        re.I,
    )
    if m:
        data["Invoice Date"] = m.group(1)

    # Customer / Bill To
    m = re.search(
        r"(Customer|Client|Bill\s*To)\s*Name?\s*[:\-]?\s*([A-Za-z\s]+)",
        text,
        re.I,
    )
    if m:
        data["Customer Name"] = m.group(2).strip()

    # Total Amount
    m = re.search(r"(Grand\s*Total|Total\s*Amount)\s*[:\-]?\s*(\d[\d,\.]*)", text, re.I)
    if m:
        data["Total Amount"] = float(m.group(2).replace(",", ""))

    # Invoice Type
    if "tax invoice" in text.lower():
        data["Invoice Type"] = "Tax Invoice"

    return data


# ==============================
# PROCESS FILE
# ==============================
def process_file(path):
    if path.lower().endswith(".pdf"):
        text = extract_text_from_pdf(path)
    else:
        text = extract_text_from_image(path)

    if not text.strip():
        return {"Filename": os.path.basename(path), "Status": "OCR Failed"}

    data = auto_extract_fields(text)
    data["Filename"] = os.path.basename(path)
    data["Status"] = "Success"
    return data


# ==============================
# STREAMLIT UI
# ==============================
st.set_page_config("Smart Invoice Extractor", layout="centered")
st.title("📄 Smart Invoice Extractor")
st.caption("Auto Column • Business & Tax Invoice OCR")

uploaded_files = st.file_uploader(
    "Upload Invoice Files",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

if st.button("🚀 Start Extraction"):
    if not uploaded_files:
        st.warning("Please upload at least one invoice")
        st.stop()

    results = []
    temp_dir = tempfile.mkdtemp()

    for file in uploaded_files:
        path = os.path.join(temp_dir, file.name)
        with open(path, "wb") as f:
            f.write(file.getbuffer())
        results.append(process_file(path))

    df = pd.DataFrame(results).fillna("")

    # ==============================
    # ADD SR NUMBER
    # ==============================
    df.insert(0, "Sr No", range(1, len(df) + 1))

    st.success(f"Processed {len(df)} invoices")
    st.dataframe(df, use_container_width=True)

    # ==============================
    # EXCEL EXPORT
    # ==============================
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    st.download_button(
        "⬇️ Download Excel",
        data=excel_buffer.getvalue(),
        file_name=f"invoice_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption("Auto-detects fields • Dynamic columns • Streamlit Cloud safe")
