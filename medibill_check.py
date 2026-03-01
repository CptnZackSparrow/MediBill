#!/usr/bin/env python3
"""
MediBillCheck — AI Medical Bill Overcharge Detector
Uses Google Gemini API (FREE) to extract CPT codes, compares to regional
pricing, flags overcharges, and generates dispute letters.

Usage:
    python medibill_check.py                  # Interactive mode
    python medibill_check.py --demo           # Run with built-in sample bill
    python medibill_check.py --file bill.txt  # Analyze a bill file

Setup (FREE — no credit card needed):
    1. Go to console.groq.com
    2. Sign in with Google → Get API Key
    3. set GROQ_API_KEY=your-key-here   (Windows CMD)
       export GROQ_API_KEY=your-key-here (Mac/Linux)

Requires:
    pip install requests   # usually already installed
    pip install pypdf2     # optional, for PDF support
"""
# cd desktop
# cd medbill_hackathon
# python medibill_check.py --file bill.txt

import os
import sys
import json
import re
import textwrap
import argparse
from datetime import date

# ─────────────────────────────────────────────
# CPT CODE REGIONAL PRICING DATABASE
# (avg, high) in USD — national averages
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
    "90658": {"name": "Influenza Vaccine (≥3 years)",          "avg": 28,    "high": 42},
    "90714": {"name": "Tetanus Toxoid (unpreserved)",          "avg": 35,    "high": 55},
    "27447": {"name": "Total Knee Replacement",                "avg": 15800, "high": 22000},
    "29881": {"name": "Knee Arthroscopy with Meniscectomy",    "avg": 4200,  "high": 6100},
    "43239": {"name": "Upper GI Endoscopy with Biopsy",        "avg": 1200,  "high": 1800},
    "45378": {"name": "Diagnostic Colonoscopy",                "avg": 1100,  "high": 1650},
    "45380": {"name": "Colonoscopy with Biopsy",               "avg": 1350,  "high": 1950},
    "99291": {"name": "Critical Care (first 30-74 min)",       "avg": 480,   "high": 680},
    "99292": {"name": "Critical Care (additional 30 min)",     "avg": 220,   "high": 320},
}

# ─────────────────────────────────────────────
# SAMPLE BILL FOR DEMO MODE
# ─────────────────────────────────────────────
SAMPLE_BILL = """
MEMORIAL GENERAL HOSPITAL — PATIENT INVOICE
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
TOTAL DUE:                                            $3,477.00
"""

# ─────────────────────────────────────────────
# ANSI COLOR HELPERS
# ─────────────────────────────────────────────
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    AMBER  = "\033[33m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    GRAY   = "\033[90m"
    BG_RED = "\033[41m"

def supports_color():
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = supports_color()

def c(color, text):
    return f"{color}{text}{C.RESET}" if USE_COLOR else text

def box(text, width=70, color=C.CYAN):
    line = "─" * width
    return f"{c(color, '┌' + line + '┐')}\n{c(color, '│')} {text.center(width - 1)}{c(color, '│')}\n{c(color, '└' + line + '┘')}"

def divider(width=72, char="─", color=C.GRAY):
    return c(color, char * width)

def header_bar(title, width=72):
    pad = width - len(title) - 4
    left = pad // 2
    right = pad - left
    return c(C.AMBER, "━" * left + "  " + C.BOLD + title + C.RESET + C.AMBER + "  " + "━" * right + C.RESET)

# ─────────────────────────────────────────────
# CLAUDE API CLIENT
# ─────────────────────────────────────────────
def call_gemini(prompt: str, max_tokens: int = 1500) -> str:
    """Call Groq API (free tier — no credit card needed)."""
    import requests as req

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable not set.\n"
            "Get a free key at console.groq.com, then run:\n"
            "  Windows CMD:  set GROQ_API_KEY=your-key-here\n"
            "  Mac/Linux:    export GROQ_API_KEY=your-key-here"
        )

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = req.post(url, headers=headers, json=payload, timeout=60)
    if not resp.ok:
        raise ValueError(f"API {resp.status_code}: {resp.text}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# STEP 1: EXTRACT BILL DATA VIA CLAUDE
# ─────────────────────────────────────────────
def extract_bill(bill_text: str) -> dict:
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
- Extract EVERY charge line, including duplicates as separate entries
- billed_amount is a number (no $ or commas)
- If no CPT code is visible, use "UNKNOWN" for code
- quantity is how many times this specific line appears consecutively"""

    raw = call_gemini(prompt, max_tokens=1500)
    clean = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Try to find JSON if extra text leaked through
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        clean = match.group(0)

    return json.loads(clean)


# ─────────────────────────────────────────────
# STEP 2: LOCAL ANALYSIS (no API needed)
# ─────────────────────────────────────────────
def analyze_charges(bill: dict) -> dict:
    items = bill.get("line_items", [])
    analyzed = []
    total_overcharge = 0.0
    flags = []

    # Track code occurrences for duplicate detection
    code_seen = {}
    for item in items:
        code = item.get("code", "UNKNOWN")
        code_seen[code] = code_seen.get(code, 0) + 1

    code_occurrence = {}  # tracks how many times we've seen each code so far

    for item in items:
        code = item.get("code", "UNKNOWN")
        billed = float(item.get("billed_amount", 0))
        desc = item.get("description", "Unknown Service")

        ref = CPT_PRICING.get(code)
        severity = "ok"
        flag_msg = None
        overcharge = 0.0
        is_duplicate = False

        # ── Duplicate check ──
        code_occurrence[code] = code_occurrence.get(code, 0) + 1
        if code_seen.get(code, 1) > 1 and code_occurrence[code] > 1:
            is_duplicate = True
            overcharge += billed
            severity = "critical"
            flag_msg = f"DUPLICATE CHARGE #{code_occurrence[code]} (same code billed {code_seen[code]}x)"

        # ── Price check ──
        if ref and not is_duplicate:
            avg, high = ref["avg"], ref["high"]
            ratio = billed / avg if avg > 0 else 1

            if billed > high * 1.5:
                overcharge = billed - high
                severity = "critical"
                flag_msg = f"Billed {ratio:.0%} of avg · exceeds high-end by ${billed - high:,.0f} (avg ${avg}, high ${high})"
            elif billed > high:
                overcharge = billed - high
                severity = "warning"
                flag_msg = f"Above regional high of ${high} by ${billed - high:,.0f} (avg ${avg})"
            elif billed > avg * 1.35:
                severity = "caution"
                flag_msg = f"35%+ above regional average of ${avg}"
        elif ref and is_duplicate:
            # Append pricing context to duplicate flag
            flag_msg += f" · Reference avg ${ref['avg']}"

        total_overcharge += overcharge

        entry = {
            **item,
            "ref": ref,
            "severity": severity,
            "flag": flag_msg,
            "overcharge": round(overcharge, 2),
            "is_duplicate": is_duplicate,
        }
        analyzed.append(entry)
        if flag_msg:
            flags.append(entry)

    # Risk score: weighted combo of flag ratio and overcharge ratio
    flag_ratio = len(flags) / max(len(items), 1)
    total_billed = float(bill.get("total_billed", 1) or 1)
    overcharge_ratio = total_overcharge / total_billed
    risk_score = min(100, int(flag_ratio * 55 + overcharge_ratio * 100))

    return {
        **bill,
        "analyzed": analyzed,
        "flags": flags,
        "total_overcharge": round(total_overcharge, 2),
        "risk_score": risk_score,
    }


# ─────────────────────────────────────────────
# STEP 3: GENERATE DISPUTE LETTER VIA CLAUDE
# ─────────────────────────────────────────────
def generate_dispute_letter(result: dict) -> str:
    flags_summary = "\n".join(
        f"  - CPT {f['code']} ({f['description']}): "
        f"Billed ${f['billed_amount']:,.2f}, issue: {f['flag']}"
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
2. Clear subject line referencing account/invoice
3. Opening paragraph identifying yourself and the bill
4. Body listing each flagged charge with specific concerns (duplicates, overpricing)
5. Specific requests: itemized bill review, correction of duplicate charges, written justification for prices exceeding regional averages
6. Closing requesting written response within 30 days, threatening escalation to state insurance commissioner
7. Professional sign-off with [YOUR NAME] and contact info placeholders

Tone: assertive but professional. No markdown formatting."""

    return call_gemini(prompt, max_tokens=1200)


# ─────────────────────────────────────────────
# DISPLAY FUNCTIONS
# ─────────────────────────────────────────────
def severity_color(severity):
    return {
        "critical": C.RED,
        "warning":  C.YELLOW,
        "caution":  C.AMBER,
        "ok":       C.GREEN,
    }.get(severity, C.GRAY)

def severity_label(severity):
    return {
        "critical": "[CRITICAL]",
        "warning":  "[WARNING] ",
        "caution":  "[CAUTION] ",
        "ok":       "[  OK   ] ",
    }.get(severity, "[UNKNOWN] ")

def risk_bar(score, width=30):
    filled = int(score / 100 * width)
    bar_color = C.RED if score > 60 else C.YELLOW if score > 30 else C.GREEN
    bar = "█" * filled + "░" * (width - filled)
    return c(bar_color, bar) + f" {score}/100"

def print_results(result: dict):
    W = 72
    print()
    print(header_bar("MEDIBILLCHECK — ANALYSIS RESULTS", W))
    print()

    # ── Bill Info ──
    print(c(C.GRAY, "  PATIENT  ") + c(C.WHITE, result.get("patient", "Unknown")))
    print(c(C.GRAY, "  PROVIDER ") + c(C.WHITE, result.get("provider", "Unknown")))
    print(c(C.GRAY, "  DATE     ") + c(C.WHITE, result.get("date", "Unknown")))
    print()

    # ── Summary Cards ──
    total_billed    = result.get("total_billed", 0)
    total_overcharge = result.get("total_overcharge", 0)
    risk_score      = result.get("risk_score", 0)
    flags           = result.get("flags", [])

    print(divider(W))
    print()
    billed_str    = f"  Total Billed:         {c(C.WHITE, f'${total_billed:>10,.2f}')}"
    overcharge_str = f"  Potential Overcharge: {c(C.RED if total_overcharge > 0 else C.GREEN, f'${total_overcharge:>10,.2f}')}"
    analyzed_count = len(result.get("analyzed", []))
    flagged_str    = f"  Charges Flagged:      {c(C.YELLOW if flags else C.GREEN, f'{len(flags):>10} / {analyzed_count}')}"
    print(billed_str)
    print(overcharge_str)
    print(flagged_str)
    print(f"  Risk Score:           {risk_bar(risk_score)}")
    print()
    print(divider(W))

    # ── Charge Table ──
    print()
    print(c(C.BOLD, f"  {'CODE':<8} {'DESCRIPTION':<32} {'BILLED':>9}  {'AVG':>7}  STATUS"))
    print(divider(W, "─"))

    for item in result.get("analyzed", []):
        code     = item.get("code", "?????")
        desc     = item.get("description", "")[:31]
        billed   = item.get("billed_amount", 0)
        ref      = item.get("ref")
        avg_str  = f"${ref['avg']:>6,.0f}" if ref else "  N/A  "
        sev      = item.get("severity", "ok")
        slabel   = severity_label(sev)
        flag     = item.get("flag", "")

        amount_color = severity_color(sev) if sev != "ok" else C.WHITE
        row = (
            f"  {c(C.GRAY, code):<8} "
            f"{desc:<32} "
            f"{c(amount_color, f'${billed:>8,.2f}')}  "
            f"{c(C.DIM, avg_str)}  "
            f"{c(severity_color(sev), slabel)}"
        )
        print(row)

        if flag:
            wrapped = textwrap.wrap(flag, width=55)
            for i, line in enumerate(wrapped):
                prefix = "  └─ " if i == 0 else "     "
                print(c(severity_color(sev), f"{prefix}{line}"))
        print()

    print(divider(W))

    # ── Flags Summary ──
    if flags:
        print()
        print(c(C.RED + C.BOLD, f"  ⚠  {len(flags)} SUSPICIOUS CHARGE(S) DETECTED"))
        print(c(C.AMBER, f"     Estimated overcharge: ${total_overcharge:,.2f}"))
        print()

        for f in flags:
            print(c(severity_color(f["severity"]),
                f"  • CPT {f['code']}: {f['description'][:40]} "
                f"— ${f['overcharge']:,.2f} flagged"
            ))
        print()
    else:
        print()
        print(c(C.GREEN + C.BOLD, "  ✓  No significant overcharges detected."))
        print()


def print_dispute_letter(letter: str):
    W = 72
    print()
    print(header_bar("DISPUTE LETTER", W))
    print()
    for line in letter.split("\n"):
        print("  " + line)
    print()
    print(divider(W))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def get_bill_text(args) -> str:
    """Get bill text from CLI args, file, or interactive prompt."""
    if args.demo:
        print(c(C.GRAY, "\n  [Demo mode] Using built-in sample bill...\n"))
        return SAMPLE_BILL

    if args.file:
        path = args.file
        if path.lower().endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(path)
                return "\n".join(page.extract_text() for page in reader.pages)
            except ImportError:
                try:
                    import PyPDF2
                    with open(path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        return "\n".join(p.extract_text() for p in reader.pages)
                except ImportError:
                    print(c(C.RED, "  PDF support requires: pip install pypdf"))
                    sys.exit(1)
        else:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    # Interactive
    print(c(C.CYAN, "\n  Paste your medical bill text below."))
    print(c(C.GRAY, "  When done, enter a blank line followed by END\n"))
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="MediBillCheck — AI Medical Bill Overcharge Detector"
    )
    parser.add_argument("--demo",    action="store_true", help="Run with built-in sample bill")
    parser.add_argument("--file",    metavar="PATH",      help="Path to bill (.txt or .pdf)")
    parser.add_argument("--no-letter", action="store_true", help="Skip dispute letter generation")
    parser.add_argument("--save",    metavar="PATH",      help="Save dispute letter to file")
    args = parser.parse_args()

    # ── Banner ──
    W = 72
    print()
    print(c(C.AMBER + C.BOLD, "  ██╗  ██╗███████╗██████╗ ██╗██████╗ ██╗██╗     ██╗"))
    print(c(C.AMBER,          "  ███╗ ██║██╔════╝██╔══██╗██║██╔══██╗██║██║     ██║"))
    print(c(C.AMBER,          "  ██╔██╗██║█████╗  ██║  ██║██║██████╔╝██║██║     ██║"))
    print(c(C.AMBER,          "  ██║╚████║██╔══╝  ██║  ██║██║██╔══██╗██║██║     ██║"))
    print(c(C.AMBER,          "  ██║ ╚███║███████╗██████╔╝██║██████╔╝██║███████╗███████╗"))
    print(c(C.AMBER,          "  ╚═╝  ╚══╝╚══════╝╚═════╝ ╚═╝╚═════╝ ╚═╝╚══════╝╚══════╝"))
    print()
    print(c(C.WHITE + C.BOLD, "  MediBillCheck".center(W)))
    print(c(C.GRAY,           "  AI-Powered Medical Bill Overcharge Detector".center(W)))
    print(c(C.DIM,            "  $17 Billion lost annually to billing errors".center(W)))
    print()
    print(divider(W, "━", C.AMBER))
    print()

    # ── Check API key ──
    if not os.environ.get("GROQ_API_KEY"):
        print(c(C.RED, "  ✗ GROQ_API_KEY not set."))
        print(c(C.GRAY, "    Get a free key at console.groq.com"))
        print(c(C.GRAY, "    Windows: set GROQ_API_KEY=your-key-here"))
        print()

    # ── Get bill text ──
    bill_text = get_bill_text(args)
    if not bill_text.strip():
        print(c(C.RED, "\n  No bill text provided. Exiting."))
        sys.exit(1)

    # ── Step 1: Extract ──
    print(c(C.CYAN, "  [1/3] Extracting CPT codes and charges via Claude AI..."), end="", flush=True)
    try:
        bill = extract_bill(bill_text)
        print(c(C.GREEN, f" ✓  ({len(bill.get('line_items', []))} line items found)"))
    except json.JSONDecodeError as e:
        print(c(C.RED, f"\n  ✗ Failed to parse Claude response: {e}"))
        sys.exit(1)
    except Exception as e:
        print(c(C.RED, f"\n  ✗ API error: {e}"))
        sys.exit(1)

    # ── Step 2: Analyze ──
    print(c(C.CYAN, "  [2/3] Comparing against regional pricing database..."), end="", flush=True)
    result = analyze_charges(bill)
    flagged = len(result.get("flags", []))
    print(c(C.GREEN if flagged == 0 else C.YELLOW, f" ✓  ({flagged} flag(s) raised)"))

    # ── Display Results ──
    print_results(result)

    # ── Step 3: Dispute Letter ──
    if result.get("flags") and not args.no_letter:
        print()
        print(c(C.AMBER, "  Potential overcharges detected."))
        if not args.demo:
            answer = input(c(C.WHITE, "  Generate dispute letter? [Y/n]: ")).strip().lower()
            generate = answer in ("", "y", "yes")
        else:
            generate = True

        if generate:
            print(c(C.CYAN, "\n  [3/3] Generating dispute letter via Claude AI..."), end="", flush=True)
            try:
                letter = generate_dispute_letter(result)
                print(c(C.GREEN, " ✓"))
                print_dispute_letter(letter)

                if args.save:
                    with open(args.save, "w", encoding="utf-8") as f:
                        f.write(letter)
                    print(c(C.GREEN, f"  ✓ Letter saved to: {args.save}"))
                else:
                    if not args.demo:
                        save_path = input(c(C.GRAY, "  Save letter to file? (leave blank to skip): ")).strip()
                        if save_path:
                            with open(save_path, "w", encoding="utf-8") as f:
                                f.write(letter)
                            print(c(C.GREEN, f"  ✓ Saved to {save_path}"))
            except Exception as e:
                print(c(C.RED, f"\n  ✗ Letter generation failed: {e}"))

    elif not result.get("flags"):
        print(c(C.GREEN, "  ✓ No dispute letter needed — bill appears reasonable."))

    # ── Final summary ──
    print()
    print(divider(W, "━", C.AMBER))
    total_b = result.get("total_billed", 0)
    total_o = result.get("total_overcharge", 0)
    savings_pct = (total_o / total_b * 100) if total_b else 0
    print(c(C.WHITE + C.BOLD, f"\n  SUMMARY:  ${total_b:,.2f} billed  ·  "
          + (c(C.RED, f"${total_o:,.2f} flagged ({savings_pct:.1f}%) ") if total_o > 0
             else c(C.GREEN, "No overcharges detected "))))
    print()
    print(c(C.DIM, "  Disclaimer: For informational purposes only. Not legal or financial advice."))
    print(c(C.DIM, "  Always consult your insurance provider and a billing advocate for disputes."))
    print()


if __name__ == "__main__":
    main()