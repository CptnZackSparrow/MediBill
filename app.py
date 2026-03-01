import streamlit as st
import json
import re
import os
import requests

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="MediBillCheck",
    page_icon="🏥",
    layout="wide",
)

# ─────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #ffffff;
    color: #111111;
}
.stApp { background-color: #f8f9fa; }
.stSidebar { background-color: #ffffff !important; border-right: 1px solid #e5e7eb; }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; color: #111111 !important; }

p, li, span, div { color: #111111; }

.metric-card {
    background: #ffffff;
    border: 1.5px solid #e5e7eb;
    border-radius: 10px;
    padding: 20px 24px;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.metric-label {
    font-size: 11px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: #6b7280;
    margin-bottom: 8px;
    font-weight: 600;
}
.metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #111111;
}

.section-header {
    font-size: 11px;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #6b7280;
    border-bottom: 2px solid #e5e7eb;
    padding-bottom: 8px;
    margin-bottom: 16px;
    font-weight: 600;
}

.dispute-letter {
    background: #f9fafb;
    border: 1.5px solid #e5e7eb;
    border-radius: 8px;
    padding: 28px;
    font-size: 13px;
    line-height: 1.9;
    white-space: pre-wrap;
    color: #111111;
}

.stButton > button {
    background: #c8102e !important;
    color: #ffffff !important;
    border: none !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px !important;
    border-radius: 6px !important;
    padding: 10px 28px !important;
}
.stButton > button:hover {
    background: #a00d24 !important;
}

.stTextArea textarea {
    background: #ffffff !important;
    border: 1.5px solid #d1d5db !important;
    color: #111111 !important;
    font-family: 'Inter', monospace !important;
    font-size: 13px !important;
    border-radius: 6px !important;
}
.stTextArea textarea:focus {
    border-color: #c8102e !important;
    box-shadow: 0 0 0 2px rgba(200,16,46,0.15) !important;
}

.stTextInput input {
    background: #ffffff !important;
    border: 1.5px solid #d1d5db !important;
    color: #111111 !important;
    border-radius: 6px !important;
}

.stTabs [data-baseweb="tab"] {
    color: #6b7280 !important;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #c8102e !important;
    border-bottom-color: #c8102e !important;
}

.stMarkdown p { color: #111111 !important; }

label, .stTextInput label, .stTextArea label {
    color: #374151 !important;
    font-weight: 500 !important;
}

.risk-bar-bg {
    background: #e5e7eb;
    border-radius: 4px;
    height: 10px;
    width: 100%;
    margin-top: 8px;
}
.risk-bar-fill {
    height: 10px;
    border-radius: 4px;
    transition: width 1s;
}

[data-testid="stSidebar"] * { color: #111111 !important; }
[data-testid="stSidebar"] a { color: #c8102e !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# CPT PRICING DATABASE
# ─────────────────────────────────────────────
CPT_PRICING = {
    "99213": {"name": "Office Visit (Established, Low)",       "avg": 150,   "high": 220},
    "99214": {"name": "Office Visit (Established, Moderate)",  "avg": 210,   "high": 310},
    "99215": {"name": "Office Visit (Established, Complex)",   "avg": 285,   "high": 420},
    "99203": {"name": "Office Visit (New Patient, Low)",       "avg": 175,   "high": 260},
    "99204": {"name": "Office Visit (New Patient, Moderate)",  "avg": 250,   "high": 370},
    "99283": {"name": "ED Visit (Moderate Severity)",          "avg": 380,   "high": 520},
    "99284": {"name": "ED Visit (High Severity)",              "avg": 550,   "high": 780},
    "99285": {"name": "ED Visit (High/Critical Severity)",     "avg": 750,   "high": 1050},
    "99232": {"name": "Subsequent Hospital Care",              "avg": 140,   "high": 210},
    "99233": {"name": "Subsequent Hospital Care (Complex)",    "avg": 195,   "high": 285},
    "80053": {"name": "Comprehensive Metabolic Panel",         "avg": 35,    "high": 55},
    "80048": {"name": "Basic Metabolic Panel",                 "avg": 25,    "high": 40},
    "85025": {"name": "CBC with Differential",                 "avg": 28,    "high": 45},
    "85027": {"name": "CBC without Differential",              "avg": 22,    "high": 35},
    "84443": {"name": "TSH (Thyroid Stimulating Hormone)",     "avg": 40,    "high": 65},
    "80061": {"name": "Lipid Panel",                           "avg": 30,    "high": 50},
    "82947": {"name": "Glucose Test",                          "avg": 12,    "high": 22},
    "93000": {"name": "ECG with Interpretation",               "avg": 85,    "high": 130},
    "93010": {"name": "ECG Interpretation Only",               "avg": 35,    "high": 55},
    "71046": {"name": "Chest X-Ray (2 views)",                 "avg": 140,   "high": 210},
    "71045": {"name": "Chest X-Ray (1 view)",                  "avg": 90,    "high": 140},
    "70553": {"name": "MRI Brain with Contrast",               "avg": 1800,  "high": 2600},
    "70551": {"name": "MRI Brain without Contrast",            "avg": 1400,  "high": 2000},
    "72148": {"name": "MRI Lumbar Spine without Contrast",     "avg": 1400,  "high": 2100},
    "72141": {"name": "MRI Cervical Spine without Contrast",   "avg": 1350,  "high": 2000},
    "73721": {"name": "MRI Knee without Contrast",             "avg": 1250,  "high": 1850},
    "74177": {"name": "CT Abdomen/Pelvis with Contrast",       "avg": 1100,  "high": 1650},
    "70450": {"name": "CT Head without Contrast",              "avg": 700,   "high": 1050},
    "36415": {"name": "Routine Blood Draw (Venipuncture)",     "avg": 12,    "high": 20},
    "36410": {"name": "Blood Draw (Non-routine)",              "avg": 20,    "high": 32},
    "96372": {"name": "Therapeutic Injection (IM/SQ)",         "avg": 35,    "high": 55},
    "96374": {"name": "IV Push Injection",                     "avg": 85,    "high": 130},
    "90658": {"name": "Influenza Vaccine",                     "avg": 28,    "high": 42},
    "90714": {"name": "Tetanus Toxoid",                        "avg": 35,    "high": 55},
    "27447": {"name": "Total Knee Replacement",                "avg": 15800, "high": 22000},
    "29881": {"name": "Knee Arthroscopy with Meniscectomy",    "avg": 4200,  "high": 6100},
    "43239": {"name": "Upper GI Endoscopy with Biopsy",        "avg": 1200,  "high": 1800},
    "45378": {"name": "Diagnostic Colonoscopy",                "avg": 1100,  "high": 1650},
    "45380": {"name": "Colonoscopy with Biopsy",               "avg": 1350,  "high": 1950},
    "99291": {"name": "Critical Care (first 30-74 min)",       "avg": 480,   "high": 680},
    "99292": {"name": "Critical Care (additional 30 min)",     "avg": 220,   "high": 320},
    # X-rays
    "73030": {"name": "X-Ray Shoulder (2+ views)",               "avg": 110,   "high": 180},
    "73060": {"name": "X-Ray Humerus (2+ views)",                "avg": 95,    "high": 155},
    "73020": {"name": "X-Ray Shoulder (1 view)",                 "avg": 75,    "high": 120},
    # Vaccines
    "90715": {"name": "Tdap Vaccine (7 years+)",                 "avg": 45,    "high": 75},
    "90716": {"name": "Varicella Vaccine",                       "avg": 120,   "high": 180},
    "90707": {"name": "MMR Vaccine",                             "avg": 85,    "high": 130},
    # Immunization admin
    "90471": {"name": "Immunization Admin (first injection)",    "avg": 25,    "high": 40},
    "90472": {"name": "Immunization Admin (each add'l)",         "avg": 15,    "high": 25},
}

SAMPLE_BILL = """MEMORIAL GENERAL HOSPITAL — PATIENT INVOICE
============================================
Date of Service: 01/15/2026
Patient: Jane Smith
Account #: 4829301
Provider: Dr. Robert Chen, MD

ITEMIZED CHARGES:
-----------------
99284   Emergency Department Visit (High Severity)     $1,240.00
85025   Complete Blood Count with Differential           $189.00
80053   Comprehensive Metabolic Panel                    $165.00
93000   Electrocardiogram with Interpretation            $310.00
71046   Chest X-Ray, 2 views                             $425.00
36415   Routine Venipuncture                              $89.00
99232   Subsequent Hospital Care, Day 1                  $380.00
99232   Subsequent Hospital Care, Day 2                  $380.00
36415   Routine Venipuncture                              $89.00
96372   Therapeutic Injection (IM)                       $210.00
-----------------
TOTAL DUE:                                            $3,477.00"""

# ─────────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────────
def call_groq(prompt: str, api_key: str, max_tokens: int = 1500) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if not resp.ok:
        raise ValueError(f"API error {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]


def extract_bill(bill_text: str, api_key: str) -> dict:
    prompt = f"""You are a certified medical billing specialist. Analyze this medical bill and extract every charge.

Medical Bill:
{bill_text}

Respond ONLY with valid JSON (no markdown, no backticks, no explanation):
{{
  "patient": "patient name or Unknown",
  "provider": "hospital or clinic name or Unknown",
  "date": "service date or Unknown",
  "total_billed": 0.00,
  "line_items": [
    {{"code": "XXXXX", "description": "service description", "billed_amount": 0.00, "quantity": 1}}
  ]
}}

Rules:
- Extract EVERY charge line as a SEPARATE entry — one object per row
- billed_amount is a number (no $ or commas), multiply unit price by quantity if needed
- quantity is always 1 per line item entry (expand multiple quantities into separate entries)
- If CPT codes are present, use them. If NOT present, infer the most likely CPT code from the description using your medical billing knowledge:
  * "ibuprofen", "medication", "pharmacy" type items -> use "UNKNOWN"
  * "x-ray shoulder" -> 73030
  * "ED level 3", "HC ED level 3" -> 99283
  * "ED level 4" -> 99284
  * "ED level 5" -> 99285
  * "TDAP", "immunization injection" -> 90715
  * "room and board" -> use "UNKNOWN"
  * "laboratory", "lab general" -> use "UNKNOWN"
  * "radiology" (general) -> use "UNKNOWN"
  * "dressing", "medical supplies" -> use "UNKNOWN"
  * "ECG", "EKG" -> 93000
  * "chest x-ray" -> 71046
  * "CBC", "complete blood count" -> 85025
  * "metabolic panel" -> 80053
  * "MRI" -> infer specific code based on body part
  * "CT scan" -> infer specific code based on body part
- Always make your best effort to assign a real CPT code when the description clearly maps to one
- Do NOT invent codes — only use codes you are confident about"""

    raw = call_groq(prompt, api_key, max_tokens=1500)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        clean = match.group(0)
    return json.loads(clean)


def analyze_charges(bill: dict) -> dict:
    items = bill.get("line_items", [])
    analyzed = []
    total_overcharge = 0.0
    flags = []

    code_seen = {}
    for item in items:
        code = item.get("code", "UNKNOWN")
        code_seen[code] = code_seen.get(code, 0) + 1

    code_occurrence = {}

    for item in items:
        code = item.get("code", "UNKNOWN")
        billed = float(item.get("billed_amount", 0))

        ref = CPT_PRICING.get(code)
        severity = "ok"
        flag_msg = None
        overcharge = 0.0
        is_duplicate = False

        code_occurrence[code] = code_occurrence.get(code, 0) + 1
        if code_seen.get(code, 1) > 1 and code_occurrence[code] > 1:
            is_duplicate = True
            overcharge += billed
            severity = "critical"
            flag_msg = f"Duplicate charge #{code_occurrence[code]} — same code billed {code_seen[code]}x"

        if ref and not is_duplicate:
            avg, high = ref["avg"], ref["high"]
            ratio = billed / avg if avg > 0 else 1
            if billed > high * 1.5:
                overcharge = billed - high
                severity = "critical"
                flag_msg = f"Billed {ratio:.0%} of avg — exceeds high-end by ${billed - high:,.0f} (avg ${avg}, high ${high})"
            elif billed > high:
                overcharge = billed - high
                severity = "warning"
                flag_msg = f"Above regional high of ${high} by ${billed - high:,.0f} (avg ${avg})"
            elif billed > avg * 1.35:
                severity = "caution"
                flag_msg = f"35%+ above regional average of ${avg}"
        elif ref and is_duplicate:
            flag_msg += f" (ref avg ${ref['avg']})"

        total_overcharge += overcharge
        entry = {**item, "ref": ref, "severity": severity, "flag": flag_msg,
                 "overcharge": round(overcharge, 2), "is_duplicate": is_duplicate}
        analyzed.append(entry)
        if flag_msg:
            flags.append(entry)

    flag_ratio = len(flags) / max(len(items), 1)
    total_billed = float(bill.get("total_billed", 1) or 1)
    overcharge_ratio = total_overcharge / total_billed
    risk_score = min(100, int(flag_ratio * 55 + overcharge_ratio * 100))

    return {**bill, "analyzed": analyzed, "flags": flags,
            "total_overcharge": round(total_overcharge, 2), "risk_score": risk_score}


def generate_dispute_letter(result: dict, api_key: str) -> str:
    flags_summary = "\n".join(
        f"  - CPT {f['code']} ({f['description']}): Billed ${f['billed_amount']:,.2f}, issue: {f['flag']}"
        for f in result["flags"]
    )
    prompt = f"""Write a professional medical bill dispute letter.

Patient: {result['patient']}
Provider: {result['provider']}
Date of Service: {result['date']}
Total Billed: ${result['total_billed']:,.2f}
Total Potential Overcharge: ${result['total_overcharge']:,.2f}

Flagged Charges:
{flags_summary}

Write a firm, professional dispute letter with:
1. Header with [YOUR NAME], [YOUR ADDRESS], [DATE] placeholders
2. Clear subject line
3. Opening paragraph identifying yourself and the bill
4. Body listing each flagged charge with specific concerns
5. Requests: itemized bill review, duplicate charge correction, price justification
6. Closing requesting response within 30 days
7. Professional sign-off with [YOUR NAME] placeholder

Tone: assertive but professional. No markdown formatting."""
    return call_groq(prompt, api_key, max_tokens=1200)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
SEV_COLOR = {"critical": "#ff3b30", "warning": "#ff9500", "caution": "#ffcc00", "ok": "#34c759"}
SEV_EMOJI = {"critical": "🔴", "warning": "🟠", "caution": "🟡", "ok": "✅"}
SEV_LABEL = {"critical": "CRITICAL", "warning": "WARNING", "caution": "CAUTION", "ok": "OK"}


def render_metric(label, value, color="#f0ede8", sublabel=""):
    sub = f'<div style="font-size:11px;color:#6b7280;margin-top:4px">{sublabel}</div>' if sublabel else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{color}">{value}</div>
        {sub}
    </div>""", unsafe_allow_html=True)


def render_risk_bar(score):
    color = SEV_COLOR["critical"] if score > 60 else SEV_COLOR["warning"] if score > 30 else SEV_COLOR["ok"]
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Risk Score</div>
        <div class="metric-value" style="color:{color}">{score}/100</div>
        <div class="risk-bar-bg">
            <div class="risk-bar-fill" style="width:{score}%;background:{color}"></div>
        </div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

# Header
st.markdown("""
<div style="border-bottom:2px solid #e5e7eb;padding-bottom:24px;margin-bottom:32px">
    <h1 style="font-family:'Space Grotesk',sans-serif;font-size:36px;margin:0;letter-spacing:-1px">
        MediBill<span style="color:#c8102e">Check</span>
    </h1>
    <p style="color:#6b7280;font-size:11px;letter-spacing:2px;text-transform:uppercase;margin:4px 0 0">
        AI-Powered Medical Bill Overcharge Detector
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar — API key
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown('<p style="font-size:11px;color:#666">Get a free API key at<br><a href="https://console.groq.com" style="color:#e8d5b0">console.groq.com</a></p>', unsafe_allow_html=True)
    api_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
    st.markdown("---")
    st.markdown('<p style="font-size:10px;color:#444;letter-spacing:1px">CPT DATABASE</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:12px;color:#666">{len(CPT_PRICING)} codes loaded</p>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<p style="font-size:10px;color:#333">Not legal or financial advice.<br>For informational use only.</p>', unsafe_allow_html=True)

# Tabs
tab1, tab2 = st.tabs(["📋 Upload Bill", "🔍 Analysis"])

with tab1:
    st.markdown('<div class="section-header">Input Your Medical Bill</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        bill_text = st.text_area(
            "Paste bill text here",
            height=300,
            placeholder="Paste your itemized medical bill here...\n\nAny format works — CPT codes, plain text, messy OCR, etc.",
            label_visibility="collapsed"
        )
    with col2:
        uploaded = st.file_uploader("Or upload a .txt file", type=["txt"])
        if uploaded:
            bill_text = uploaded.read().decode("utf-8")
            st.success(f"✓ {uploaded.name} loaded")

        st.markdown("---")
        if st.button("Load Sample Bill", use_container_width=True):
            st.session_state["sample_loaded"] = True
            st.rerun()

    if st.session_state.get("sample_loaded"):
        bill_text = SAMPLE_BILL
        st.session_state["sample_loaded"] = False
        st.info("Sample bill loaded — click Analyze Bill!")

    st.markdown("")
    analyze_clicked = st.button("→ Analyze Bill", use_container_width=False)

    if analyze_clicked:
        if not api_key:
            st.error("⚠️ Enter your Groq API key in the sidebar first.")
        elif not bill_text or not bill_text.strip():
            st.error("⚠️ Please paste your bill text or upload a file.")
        else:
            with st.spinner("🔍 Extracting CPT codes via AI..."):
                try:
                    bill = extract_bill(bill_text, api_key)
                    st.session_state["bill_raw"] = bill
                except Exception as e:
                    st.error(f"Extraction failed: {e}")
                    st.stop()

            with st.spinner("📊 Comparing against regional pricing database..."):
                result = analyze_charges(bill)
                st.session_state["result"] = result

            st.success(f"✓ Analysis complete — {len(result['flags'])} issue(s) found!")
            st.info("👆 Switch to the **Analysis** tab to see results.")

with tab2:
    result = st.session_state.get("result")

    if not result:
        st.markdown("""
        <div style="text-align:center;padding:80px 20px;color:#333">
            <div style="font-size:48px;margin-bottom:16px">⚕️</div>
            <div style="font-size:14px">Upload and analyze a bill first</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Bill info
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<p style="color:#6b7280;font-size:11px;margin:0;font-weight:600;letter-spacing:1px;text-transform:uppercase">PATIENT</p><p style="color:#111111;margin:0;font-weight:500">{result.get("patient","Unknown")}</p>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<p style="color:#6b7280;font-size:11px;margin:0;font-weight:600;letter-spacing:1px;text-transform:uppercase">PROVIDER</p><p style="color:#111111;margin:0;font-weight:500">{result.get("provider","Unknown")}</p>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<p style="color:#6b7280;font-size:11px;margin:0;font-weight:600;letter-spacing:1px;text-transform:uppercase">DATE</p><p style="color:#111111;margin:0;font-weight:500">{result.get("date","Unknown")}</p>', unsafe_allow_html=True)

        st.markdown("---")

        # Metrics
        m1, m2, m3 = st.columns(3)
        total_b = result.get("total_billed", 0)
        total_o = result.get("total_overcharge", 0)
        flags   = result.get("flags", [])

        with m1:
            render_metric("Total Billed", f"${total_b:,.2f}",
                          sublabel=f"{len(result.get('analyzed',[]))} line items")
        with m2:
            oc_color = SEV_COLOR["critical"] if total_o > 0 else SEV_COLOR["ok"]
            render_metric("Potential Overcharge",
                          f"${total_o:,.2f}" if total_o > 0 else "✓ $0.00",
                          color=oc_color,
                          sublabel=f"{len(flags)} charge(s) flagged")
        with m3:
            render_risk_bar(result.get("risk_score", 0))

        st.markdown("---")

        # Charge table
        st.markdown("**Itemized Charge Review**")
        st.markdown("---")

        SEV_ICONS = {"critical": "🔴", "warning": "🟠", "caution": "🟡", "ok": "✅"}
        SEV_LABELS = {"critical": "CRITICAL", "warning": "WARNING", "caution": "CAUTION", "ok": "OK"}

        for item in result.get("analyzed", []):
            sev    = item.get("severity", "ok")
            code   = item.get("code", "?????")
            desc   = item.get("description", "Unknown")
            billed = float(item.get("billed_amount", 0))
            flag   = item.get("flag", "")
            ref    = item.get("ref")
            oc     = float(item.get("overcharge", 0))
            avg_str = f"avg ${ref['avg']:,}" if ref else "not in database"
            icon   = SEV_ICONS.get(sev, "")
            label  = SEV_LABELS.get(sev, "")

            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.markdown(f"{icon} **{desc}**")
                st.caption(f"CPT {code}  ·  {avg_str}  ·  {label}")
                if flag:
                    if sev == "critical":
                        st.error(f"⚠ {flag}")
                    elif sev == "warning":
                        st.warning(f"⚠ {flag}")
                    else:
                        st.info(f"ℹ {flag}")
            with col_b:
                st.markdown(f"**${billed:,.2f}**")
                if oc > 0:
                    st.caption(f"+${oc:,.0f} over")
            st.divider()

        # Summary banner
        if total_o > 0:
            savings_pct = total_o / total_b * 100 if total_b else 0
            st.markdown(f"""
            <div style="background:#fff5f5;border:1.5px solid #fca5a5;
                        border-radius:6px;padding:20px 24px;margin-top:16px">
                <div style="font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700;color:#111111">
                    Potential savings: <span style="color:#ff3b30">${total_o:,.2f}</span>
                    <span style="font-size:13px;color:#6b7280;font-weight:400"> ({savings_pct:.1f}% of total bill)</span>
                </div>
                <div style="font-size:12px;color:#374151;margin-top:6px">
                    {len(flags)} suspicious charge(s) identified. Generate a dispute letter below to challenge these charges.
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Dispute letter
        st.markdown('<div class="section-header">Dispute Letter Generator</div>', unsafe_allow_html=True)

        if not flags:
            st.success("✅ No significant overcharges found — no dispute letter needed.")
        else:
            if st.button("✉️ Generate Dispute Letter", use_container_width=False):
                if not api_key:
                    st.error("Enter your Groq API key in the sidebar.")
                else:
                    with st.spinner("✍️ Writing your personalized dispute letter..."):
                        try:
                            letter = generate_dispute_letter(result, api_key)
                            st.session_state["letter"] = letter
                        except Exception as e:
                            st.error(f"Letter generation failed: {e}")

            if st.session_state.get("letter"):
                letter = st.session_state["letter"]
                st.markdown(f'<div class="dispute-letter">{letter}</div>', unsafe_allow_html=True)
                st.download_button(
                    "⬇️ Download Letter as .txt",
                    data=letter,
                    file_name="dispute_letter.txt",
                    mime="text/plain",
                )