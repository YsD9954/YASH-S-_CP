# backend/app.py
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .parser.extractor import StatementParser
from .parser.postprocess import PostProcessor
import tempfile
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="CardIQ Local Parser")

# Allow requests from frontend (React/Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now (dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize parser and post-processor
PARSER_CONFIG = os.path.join(BASE_DIR, "parser", "banks.yaml")
if not os.path.exists(PARSER_CONFIG):
    raise FileNotFoundError(f"Missing config file: {PARSER_CONFIG}")

parser = StatementParser(config_path=PARSER_CONFIG)
post = PostProcessor()


@app.get("/")
async def root():
    return {"message": "CardIQ Parser Backend is running. Use POST /parse/ to upload PDF."}


# heuristic bank list (edit to include your five issuers exactly how they appear in PDFs)
BANK_KEYWORDS = [
    "Axis Bank",
    "HDFC Bank",
    "SBI Card",
    "ICICI Bank",
    "Kotak",      # e.g. Kotak Mahindra
    "Citi",       # if you use Citi
]


def normalize_tokens_join(tokens):
    """
    Given a list of tokens, join consecutive single-character tokens into single words.
    This collapses sequences like: ["C","a","r","d"] -> "Card" and ["1","1","1","1"] -> "1111".
    Non-singleton tokens are kept as-is. Returns list of cleaned tokens.
    """
    out = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        if len(t) == 1:
            # accumulate a run of single-char tokens
            j = i
            run = []
            while j < n and len(tokens[j]) == 1:
                run.append(tokens[j])
                j += 1
            # if run length >= 2, join; otherwise keep single char token
            if len(run) >= 2:
                out.append("".join(run))
            else:
                out.append(run[0])
            i = j
        else:
            out.append(t)
            i += 1
    return out


def clean_text_display(text: str) -> str:
    """
    Clean extracted text for display:
    - Normalize whitespace
    - Break into tokens and collapse single-character runs (letters or digits)
    - Remove duplicate lines and join into a single readable string
    """
    if not text:
        return ""

    # Normalize whitespace and replace multiple spaces/newlines with single space
    # but we need to preserve token boundaries, so split on whitespace first
    # Keep original lines for dedup
    lines = [ln.strip() for ln in re.split(r'[\r\n]+', text) if ln.strip()]
    cleaned_lines = []
    for ln in lines:
        # split into tokens by whitespace
        tokens = ln.split()
        # collapse runs of single-character tokens
        tokens_clean = normalize_tokens_join(tokens)
        cleaned_line = " ".join(tokens_clean).strip()
        if cleaned_line:
            cleaned_lines.append(cleaned_line)

    # remove duplicate lines while preserving order
    seen = set()
    unique_lines = []
    for l in cleaned_lines:
        if l not in seen:
            seen.add(l)
            unique_lines.append(l)

    # join into one readable string
    out = " | ".join(unique_lines)  # using " | " to keep snippets readable
    # final whitespace normalize
    out = re.sub(r'\s+', ' ', out).strip()
    return out


def detect_bank_from_text(text: str) -> str:
    if not text:
        return "Unknown"
    tl = text.lower()
    for k in BANK_KEYWORDS:
        if k.lower() in tl:
            return k
    return "Unknown"


@app.post("/parse/")
async def parse_pdf(file: UploadFile = File(...)):
    """
    Upload a credit card statement PDF and extract key data points.
    Returns structured JSON with 'bank' and 'fields' where each field contains:
      - value (cleaned)
      - snippet (cleaned)
      - confidence (float between 0..1)
    The endpoint will:
      - call parser.process(tmp_path) -> raw_data
      - call post.postprocess(raw_data) -> cleaned_data (expected dict)
      - clean values/snippets before returning
      - detect bank from full_text OR from snippets/values
    """
    suffix = os.path.splitext(file.filename)[1] or ".pdf"

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        # Step 1: Parse the raw data from PDF
        raw_data = parser.process(tmp_path)

        # Step 2: Clean and format parsed data
        cleaned_data = post.postprocess(raw_data)

        # Attempt to get full text for bank detection
        pdf_text = ""
        if isinstance(raw_data, dict):
            # common keys to check
            for key in ("full_text", "text", "raw_text", "page_text"):
                if key in raw_data and isinstance(raw_data[key], str) and raw_data[key].strip():
                    pdf_text = raw_data[key]
                    break

        # Gather text to search for bank as fallback: join all snippets & values
        fallback_text_parts = []
        fields_in = cleaned_data.get("fields", {}) if isinstance(cleaned_data, dict) else {}
        for fk, fv in (fields_in.items() if isinstance(fields_in, dict) else []):
            # fv might be dict or list; support common shapes
            if isinstance(fv, dict):
                snippet = fv.get("snippet", "") or ""
                value = fv.get("value", "") or ""
                fallback_text_parts.extend([snippet, value])
            elif isinstance(fv, list):
                for item in fv:
                    if isinstance(item, dict):
                        fallback_text_parts.extend([item.get("snippet", ""), item.get("value", "")])
                    else:
                        fallback_text_parts.append(str(item))

        fallback_text = " ".join([p for p in fallback_text_parts if p])

        # Step 3: Detect bank
        bank_name = detect_bank_from_text(pdf_text)
        if bank_name == "Unknown" and fallback_text:
            bank_name = detect_bank_from_text(fallback_text)

        # Step 4: Build normalized fields output
        normalized_fields = {}
        # If cleaned_data['fields'] is not a dict, try to coerce safely
        raw_fields = cleaned_data.get("fields", {}) if isinstance(cleaned_data, dict) else {}
        if not isinstance(raw_fields, dict):
            # fallback: if it's a list-like, attempt to index into it (rare)
            raw_fields = dict(raw_fields)

        for field_key, field_val in raw_fields.items():
            # field_val may be dict {value,snippet,confidence} or list of dicts; handle both
            chosen = None
            if isinstance(field_val, dict):
                chosen = field_val
            elif isinstance(field_val, list) and field_val:
                # choose the item with highest confidence if present, else first
                best = None
                best_conf = -1.0
                for it in field_val:
                    if not isinstance(it, dict):
                        continue
                    conf = it.get("confidence", None)
                    if conf is None:
                        # try to parse numeric confidence inside string
                        try:
                            conf = float(it.get("confidence", 0))
                        except Exception:
                            conf = 0
                    if conf is not None and conf > best_conf:
                        best_conf = conf
                        best = it
                chosen = best or (field_val[0] if field_val else None)
            else:
                # fallback: convert to string
                chosen = {"value": str(field_val)}

            if not chosen or not isinstance(chosen, dict):
                continue

            raw_value = chosen.get("value", "")
            raw_snip = chosen.get("snippet", "") or ""
            raw_conf = chosen.get("confidence", None)
            # try to cast confidence to float 0..1
            try:
                conf_val = float(raw_conf) if raw_conf is not None else 0.0
                # if confidence in 0..100 scale, convert
                if conf_val > 1.0:
                    conf_val = conf_val / 100.0
            except Exception:
                conf_val = 0.0

            value_clean = clean_text_display(str(raw_value))
            snippet_clean = clean_text_display(str(raw_snip))

            # If value cleaned is empty but snippet contains the useful info, prefer snippet
            if not value_clean and snippet_clean:
                value_clean = snippet_clean

            # Normalize field key to a stable lowercase key
            normalized_key = re.sub(r'\s+', '_', field_key.strip().lower())

            normalized_fields[normalized_key] = {
                "value": value_clean,
                "snippet": snippet_clean,
                "confidence": round(conf_val, 3)
            }

        structured_data = {
            "bank": bank_name,
            "fields": normalized_fields
        }

        return {"status": "success", "data": structured_data}

    except Exception as e:
        print(f"[ERROR] Parsing failed: {e}")
        return {"status": "error", "message": str(e)}

    finally:
        # Remove temp file
        try:
            os.remove(tmp_path)
        except Exception as e:
            print(f"[WARN] Temp file not removed: {e}")
