import pdfplumber, re, yaml, os
from typing import List, Dict
import pytesseract
from PIL import Image
import numpy as np
import cv2
from sentence_transformers import SentenceTransformer, util

# Load embedding model once
EMBED_MODEL = SentenceTransformer('all-MiniLM-L6-v2')

TARGET_FIELDS = [
    "card_variant",
    "card_last4",
    "billing_cycle",
    "payment_due_date",
    "total_balance_due"
]

class StatementParser:
    def __init__(self, config_path="backend/parser/banks.yaml"):
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                self.bank_config = yaml.safe_load(f) or {}
        else:
            self.bank_config = {}

    def _page_to_image(self, page, dpi=200):
        return page.to_image(resolution=dpi).original

    def _ocr_image(self, pil_image):
        arr = np.array(pil_image.convert("RGB"))
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        blur = cv2.bilateralFilter(gray, 9, 75, 75)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        pil = Image.fromarray(th)
        txt = pytesseract.image_to_string(pil, lang='eng')
        data = pytesseract.image_to_data(pil, output_type=pytesseract.Output.DICT)
        return txt, data

    def extract_text_blocks(self, pdf_path):
        blocks_all = []
        with pdfplumber.open(pdf_path) as doc:
            for pno, page in enumerate(doc.pages):
                text = page.extract_text()
                if not text or len(text.strip()) < 20:
                    pil = self._page_to_image(page)
                    txt, _ = self._ocr_image(pil)
                    blocks_all.append({"pno": pno, "text": txt, "bbox": (0,0,page.width,page.height)})
                else:
                    blocks = page.extract_words(extra_attrs=["x0","x1","top","bottom"])
                    lines = {}
                    for w in blocks:
                        top = int(round(w['top']))
                        lines.setdefault(top, []).append(w)
                    for top, words in lines.items():
                        words = sorted(words, key=lambda x:x['x0'])
                        line_text = " ".join(w['text'] for w in words)
                        x0 = min(w['x0'] for w in words)
                        x1 = max(w['x1'] for w in words)
                        y0 = min(w['top'] for w in words)
                        y1 = max(w['bottom'] for w in words)
                        blocks_all.append({"pno": pno, "text": line_text, "bbox": (x0,y0,x1,y1)})
        return blocks_all

    def _normalize_for_match(self, s: str) -> str:
        if not s:
            return ""
        return re.sub(r"\s+", " ", s.upper()).strip()

    def _friendly_bank_name(self, bank_key: str) -> str:
        """Return proper bank display name for submission."""
        if not bank_key or bank_key == "Unknown":
            return "Unknown"
        # Check YAML first
        meta = self.bank_config.get(bank_key)
        if isinstance(meta, dict) and meta.get("display_name"):
            return meta["display_name"]
        # Fallback mapping
        fallback_map = {
            "AXIS": "Axis Bank",
            "HDFC": "HDFC Bank",
            "ICICI": "ICICI Bank",
            "SBI": "SBI",
            "KOTAK": "Kotak Mahindra Bank",
            "AMEX": "American Express",
            "CITI": "Citi Bank"
        }
        return fallback_map.get(bank_key.upper(), bank_key.replace("_", " ").title())

    def identify_bank(self, full_text: str) -> str:
        if not full_text or not full_text.strip():
            return "Unknown"
        text_norm = full_text.lower()

        # YAML check
        for bank_key, meta in self.bank_config.items():
            identifiers = []
            if isinstance(meta, dict):
                identifiers = meta.get("identifiers", [])
            tokens = [bank_key] + identifiers if bank_key else identifiers
            for ident in tokens:
                if ident and ident.lower() in text_norm:
                    return bank_key

        # Fallback mapping
        fallback_map = {
            "AXIS": "Axis Bank",
            "HDFC": "HDFC Bank",
            "ICICI": "ICICI Bank",
            "SBI": "SBI",
            "KOTAK": "Kotak Mahindra Bank",
            "AMEX": "American Express",
            "CITI": "Citi Bank"
        }
        for k in fallback_map.keys():
            if k.lower() in text_norm:
                return k  # return key for _friendly_bank_name

        return "Unknown"

    def _clean_extracted(self, s: str) -> str:
        if s is None:
            return ""
        t = str(s)
        def collapse_single_char_runs(line):
            tokens = line.split()
            out = []
            i = 0
            n = len(tokens)
            while i < n:
                if len(tokens[i]) == 1:
                    run = [tokens[i]]
                    j = i+1
                    while j < n and len(tokens[j]) == 1:
                        run.append(tokens[j]); j += 1
                    if len(run) >= 2:
                        out.append("".join(run))
                    else:
                        out.append(run[0])
                    i = j
                else:
                    out.append(tokens[i])
                    i += 1
            return " ".join(out)
        t = re.sub(r'([A-Za-z0-9])\:([A-Za-z0-9])', r'\1: \2', t)
        t = re.sub(r'(\d)(to)(\d)', r'\1 to \3', t, flags=re.I)
        t = re.sub(r'([A-Za-z0-9])to([A-Za-z0-9])', r'\1 to \2', t, flags=re.I)
        t = re.sub(r'\s+', ' ', t).strip()
        t = collapse_single_char_runs(t)
        parts = [p.strip() for p in re.split(r'[\r\n|]+', t) if p.strip()]
        unique = []
        seen = set()
        for p in parts:
            if p not in seen:
                seen.add(p); unique.append(p)
        return " | ".join(unique)

    def candidate_extraction(self, blocks: List[Dict]) -> Dict[str, List[Dict]]:
        candidates = {f: [] for f in TARGET_FIELDS}
        full_text = "\n".join(b['text'] for b in blocks)
        for b in blocks:
            raw = b['text'] or ""
            t = self._clean_extracted(raw)
            # Card Variant
            m = re.search(r'Card\s*Variant\s*:\s*([A-Za-z0-9\s]+)', t, re.I)
            if m:
                candidates['card_variant'].append({"value": m.group(1).strip(), "score": 0.95, "pno": b['pno'], "snippet": t})
            else:
                m2 = re.search(r'\b(Platinum|Gold|Regalia|Magnus|Prime|Infinite|Classic|Elite)\b', t, re.I)
                if m2:
                    candidates['card_variant'].append({"value": m2.group(1).strip(), "score": 0.7, "pno": b['pno'], "snippet": t})
            # Card last 4
            m = re.search(r'Card\s*Last\s*4\s*Digits\s*:\s*(\d{4})', t, re.I)
            if m:
                candidates['card_last4'].append({"value": m.group(1), "score": 0.98, "pno": b['pno'], "snippet": t})
            else:
                m2 = re.search(r'(?:ending|ending number|ending with|last)\s*(?:\:|\s)*\s*(\d{4})', t, re.I)
                if m2:
                    candidates['card_last4'].append({"value": m2.group(1), "score": 0.9, "pno": b['pno'], "snippet": t})
                else:
                    m3 = re.search(r'(\d{4})\b', t)
                    if m3:
                        candidates['card_last4'].append({"value": m3.group(1), "score": 0.6, "pno": b['pno'], "snippet": t})
            # Billing cycle
            m = re.search(r'Billing\s*Cycle\s*:\s*([0-9A-Za-z\-\s]+to\s+[0-9A-Za-z\-\s]+)', t, re.I)
            if m:
                candidates['billing_cycle'].append({"value": m.group(1).strip(), "score": 0.95, "pno": b['pno'], "snippet": t})
            else:
                m2 = re.search(r'(Statement\s*Period|Billing\s*Period)\s*[:\-]?\s*(.+)', t, re.I)
                if m2:
                    dates = re.findall(r'(\d{1,2}[ -/][A-Za-z]{3,}[ -/]\d{4}|\d{1,2}[ -/]\d{1,2}[ -/]\d{2,4})', m2.group(2))
                    if dates:
                        candidates['billing_cycle'].append({"value": " to ".join(dates), "score": 0.85, "pno": b['pno'], "snippet": t})
            # Payment due date
            m = re.search(r'Payment\s*Due\s*Date\s*[:\-]?\s*([0-9A-Za-z\-\s,]+)', t, re.I)
            if m:
                d = re.search(r'(\d{1,2}[ -/][A-Za-z]{3,}[ -/]\d{4}|\d{1,2}[ -/]\d{1,2}[ -/]\d{2,4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})', m.group(1))
                if d:
                    candidates['payment_due_date'].append({"value": d.group(1).strip(), "score": 0.95, "pno": b['pno'], "snippet": t})
                else:
                    candidates['payment_due_date'].append({"value": m.group(1).strip(), "score": 0.6, "pno": b['pno'], "snippet": t})
            # Total Balance Due
            m = re.search(r'(?:Total\s*Balance\s*Due|New\s*Balance|Total\s*Due|Amount\s*Due|Outstanding\s*Balance)\s*[:\-]?\s*([\$₹]?\s*[\d,]+\.\d{2})', t, re.I)
            if m:
                candidates['total_balance_due'].append({"value": m.group(1).strip(), "score": 0.98, "pno": b['pno'], "snippet": t})
            else:
                m2 = re.search(r'([\$₹]\s*[\d,]+\.\d{2})', t)
                if m2:
                    candidates['total_balance_due'].append({"value": m2.group(1).strip(), "score": 0.6, "pno": b['pno'], "snippet": t})
        return candidates

    def semantic_rerank(self, field: str, candidates: List[dict], full_text: str) -> dict:
        question_map = {
            "card_variant": "credit card type such as Platinum, Regalia, Magnus",
            "card_last4": "last four digits of the card",
            "billing_cycle": "billing cycle or statement period",
            "payment_due_date": "payment due date",
            "total_balance_due": "total balance due or amount payable"
        }
        if not candidates:
            chunks = [line.strip() for line in full_text.splitlines() if line.strip()]
            if not chunks:
                return {"value": None, "score": 0.0, "pno": None, "snippet": None}
            emb_chunks = EMBED_MODEL.encode(chunks, convert_to_tensor=True)
            q_emb = EMBED_MODEL.encode(question_map[field], convert_to_tensor=True)
            sims = util.cos_sim(q_emb, emb_chunks)[0]
            best_idx = int(sims.argmax())
            return {"value": chunks[best_idx], "score": float(sims[best_idx]), "pno": None, "snippet": chunks[best_idx]}
        texts = [c.get('value') or c.get('snippet') or "" for c in candidates]
        emb_texts = EMBED_MODEL.encode(texts, convert_to_tensor=True)
        q_emb = EMBED_MODEL.encode(question_map[field], convert_to_tensor=True)
        sims = util.cos_sim(q_emb, emb_texts)[0].cpu().numpy()
        best_idx = 0
        best_score = -1.0
        for i, c in enumerate(candidates):
            heuristic = float(c.get("score", 0.0))
            sem = float(sims[i]) if len(sims) > i else 0.0
            composite = 0.7 * heuristic + 0.3 * sem
            if composite > best_score:
                best_score = composite
                best_idx = i
        chosen = candidates[best_idx]
        return {"value": chosen.get("value", chosen.get("snippet")), "score": best_score, "pno": chosen.get("pno"), "snippet": chosen.get("snippet")}

    def process(self, pdf_path: str) -> dict:
        blocks = self.extract_text_blocks(pdf_path)
        full_text = "\n".join(b['text'] for b in blocks)
        bank_key = self.identify_bank(full_text)
        bank_display = self._friendly_bank_name(bank_key)  # Final friendly bank name
        candidates = self.candidate_extraction(blocks)
        results = {"bank": bank_display, "fields": {}}
        for field in TARGET_FIELDS:
            chosen = self.semantic_rerank(field, candidates.get(field, []), full_text)
            val_raw = chosen.get("value")
            snip_raw = chosen.get("snippet")
            val = self._clean_extracted(val_raw) if val_raw is not None else ""
            snip = self._clean_extracted(snip_raw) if snip_raw is not None else ""
            results["fields"][field] = {
                "value": val,
                "confidence": round(float(chosen.get("score", 0.0)) * 100, 1),
                "page": chosen.get("pno"),
                "snippet": snip
            }
        return results
