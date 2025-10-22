import React, { useState } from "react";
import axios from "axios";
import "./styles.css";

export default function App() {
  const [file, setFile] = useState(null);
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);

  const upload = async () => {
    if (!file) return alert("Please choose a PDF file first!");
    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const r = await axios.post("http://127.0.0.1:8000/parse/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      if (r.data.status === "success") {
        setRes(r.data.data);
      } else {
        alert("Parsing failed: " + r.data.message);
      }
    } catch (e) {
      console.error(e);
      alert("Error uploading file!");
    } finally {
      setLoading(false);
    }
  };

  // Clean text and remove common prefixes like "BillingCycle:"
  const cleanText = (t) => {
    if (!t) return "";
    t = t.replace(
      /^(BillingCycle|Card Type|Card Last 4 Digits|Payment Due Date|Total Balance Due)\s*[:\-]?\s*/i,
      ""
    );
    return t.replace(/\s+/g, " ").replace(/\s([:;])/g, "$1").trim();
  };

  return (
    <div className="container">
      <h1>CardIQ</h1>
      <p className="subtitle">Credit Card Statement Parser • Local</p>

      <div className="upload-section">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button onClick={upload} disabled={loading}>
          {loading ? "Parsing..." : "Upload & Parse"}
        </button>
      </div>

      {res && (
        <div className="result-card">
          <h2>Parsed Statement</h2>
          <div className="field">
            <span className="label">Card Type:</span>
            <span className="value">{cleanText(res.fields?.card_variant?.value)}</span>
          </div>
          <div className="field">
            <span className="label">Card Last 4 Digits:</span>
            <span className="value">{cleanText(res.fields?.card_last4?.value)}</span>
          </div>
          <div className="field">
            <span className="label">Billing Cycle:</span>
            <span className="value">{cleanText(res.fields?.billing_cycle?.value)}</span>
          </div>
          <div className="field">
            <span className="label">Payment Due Date:</span>
            <span className="value">{cleanText(res.fields?.payment_due_date?.value)}</span>
          </div>
          <div className="field">
            <span className="label">Total Balance Due:</span>
            <span className="value total">{cleanText(res.fields?.total_balance_due?.value)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
