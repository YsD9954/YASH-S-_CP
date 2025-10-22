# backend/parser/postprocess.py
import re
from datetime import datetime

class PostProcessor:
    def __init__(self):
        pass

    def _normalize_amount(self, raw):
        if not raw: return None
        s = str(raw)
        # remove currency symbols/words
        s = s.replace("₹", "").replace("Rs.", "").replace("INR", "").replace(",", "").strip()
        m = re.search(r'\d+(\.\d+)?', s)
        return float(m.group(0)) if m else None

    def _normalize_date(self, raw):
        if not raw: return None
        s = raw.strip()
        # Try a few date formats
        fmts = ["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d %b, %Y"]
        for f in fmts:
            try:
                dt = datetime.strptime(s, f)
                return dt.strftime("%Y-%m-%d")
            except:
                pass
        # try to extract dd mm yyyy tokens
        m = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', s)
        if m:
            return m.group(1)
        return s

    def postprocess(self, data):
        fields = data.get("fields", {})
        # Normalize amounts and dates
        if "total_balance_due" in fields:
            fields["total_balance_due"]["value_norm"] = self._normalize_amount(fields["total_balance_due"]["value"])
        if "payment_due_date" in fields:
            fields["payment_due_date"]["value_norm"] = self._normalize_date(fields["payment_due_date"]["value"])
        if "billing_cycle" in fields:
            bc = fields["billing_cycle"]["value"]
            if bc and isinstance(bc, str) and "to" in bc:
                parts = [p.strip() for p in bc.split("to")]
                fields["billing_cycle"]["start_norm"] = self._normalize_date(parts[0]) if parts else None
                fields["billing_cycle"]["end_norm"] = self._normalize_date(parts[1]) if len(parts)>1 else None
        return data
