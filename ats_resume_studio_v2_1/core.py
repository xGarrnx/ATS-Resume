"""
ATS Resume Studio V2.1 - core logic (no GUI).

Everything here works offline with simple rules. Tailoring only REORDERS
what is already in your master resume and mentions job keywords that your
resume already supports. It never invents experience.
"""
import copy
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

APP_DIR = Path(__file__).resolve().parent
MASTER_PATH = APP_DIR / "master_resume.json"
OUTPUT_DIR = APP_DIR / "output"

# --------------------------------------------------------------------------
# Keyword dictionary: display name -> regex (case-insensitive, word-bounded)
# --------------------------------------------------------------------------
KEYWORDS = {
    "Help Desk": r"help\s?desk",
    "Service Desk": r"service\s?desk",
    "Desktop Support": r"desktop support",
    "Technical Support": r"tech(?:nical)? support",
    "IT Support": r"it support",
    "Troubleshooting": r"troubleshoot\w*",
    "Problem Solving": r"problem[- ]solv\w*",
    "Windows": r"windows",
    "macOS": r"mac ?os",
    "iOS / iPhone": r"ios|iphone|ipad",
    "Android": r"android",
    "Mobile Devices": r"mobile device\w*|smartphone\w*",
    "Active Directory": r"active directory",
    "Microsoft 365": r"(?:microsoft|office) ?365|m365|o365",
    "Microsoft Office": r"microsoft office|ms office",
    "Outlook": r"outlook",
    "Microsoft Teams": r"microsoft teams|ms teams",
    "Azure / Entra ID": r"azure(?: ad| active directory)?|entra(?: id)?",
    "Intune / MDM": r"intune|mdm|mobile device management",
    "SCCM / Endpoint Manager": r"sccm|configuration manager|endpoint manager",
    "Ticketing": r"ticket\w*",
    "ServiceNow": r"service ?now",
    "Jira": r"jira",
    "Zendesk": r"zendesk",
    "Remote Support": r"remote (?:support|desktop|assistance|access)|rdp|teamviewer",
    "Networking": r"network(?:s|ing)?",
    "TCP/IP": r"tcp ?/? ?ip",
    "DNS": r"dns",
    "DHCP": r"dhcp",
    "VPN": r"vpn",
    "LAN/WAN": r"lan|wan",
    "Wi-Fi": r"wi-?fi|wireless",
    "Hardware": r"hardware",
    "Software": r"software",
    "Printers": r"printer\w*",
    "Peripherals": r"peripheral\w*",
    "Repair": r"repair\w*",
    "Imaging / Deployment": r"imaging|deploy\w*|provision\w*",
    "Onboarding": r"onboard\w*|new hire\w*",
    "Account Management": r"password reset\w*|account (?:management|access|provisioning)|user accounts?",
    "Customer Service": r"customer (?:service|support)|client support",
    "Documentation": r"document\w*",
    "Escalation": r"escalat\w*",
    "Incident Management": r"incident\w*",
    "SLA": r"sla|service level",
    "ITIL": r"itil",
    "Training": r"train\w*",
    "Communication": r"communicat\w*",
    "CompTIA A+": r"comptia a\+|a\+",
    "CompTIA Network+": r"network\+",
    "CompTIA Security+": r"security\+",
    "PowerShell": r"powershell",
    "Scripting": r"script\w*",
    "Linux": r"linux",
    "Python": r"python",
    "Antivirus / Malware": r"antivirus|anti-virus|malware",
    "Backup": r"backup\w*",
    "Patching": r"patch\w*",
    "Asset Management": r"asset (?:management|tracking|inventory)|inventory",
    "VoIP / Telephony": r"voip|telephon\w*",
}

# Too generic to add to a summary sentence.
GENERIC = {"Communication", "Software", "Hardware", "Training",
           "Documentation", "Problem Solving", "Repair"}

_RX = {
    name: re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % pat, re.I)
    for name, pat in KEYWORDS.items()
}

SENIOR_RX = re.compile(
    r"\b(senior|sr\.?|lead|manager|engineer|administrator|admin|analyst|"
    r"architect|tier\s*[23]|level\s*[23]|iii|ii)\b", re.I)

HEADLINE_RULES = [
    (r"help\s?desk", "Help Desk Technician"),
    (r"service\s?desk", "Service Desk Technician"),
    (r"desktop support", "Desktop Support Technician"),
    (r"(?:it|technical|tech) support", "IT Support Technician"),
    (r"it technician|support technician|computer technician", "IT Technician"),
]


# --------------------------------------------------------------------------
# Master resume storage
# --------------------------------------------------------------------------
def load_master(path=MASTER_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_master(data, path=MASTER_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def validate_master(d):
    """Return a list of problems (empty list = OK)."""
    errs = []
    if not isinstance(d, dict):
        return ["Top level must be a JSON object { ... }."]
    for k in ("name", "headline", "contact", "summary"):
        if not isinstance(d.get(k), str):
            errs.append(f'"{k}" must be text.')
    for k in ("skills", "certifications"):
        v = d.get(k)
        if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
            errs.append(f'"{k}" must be a list of text items.')
    if "education" in d and not (
            isinstance(d["education"], list) and all(isinstance(x, str) for x in d["education"])):
        errs.append('"education" must be a list of text items.')
    for sec, fields in (("experience", ("title", "company", "dates")), ("projects", ("title",))):
        v = d.get(sec)
        if not isinstance(v, list):
            errs.append(f'"{sec}" must be a list.')
            continue
        for i, item in enumerate(v, 1):
            if not isinstance(item, dict):
                errs.append(f'"{sec}" item {i} must be an object.')
                continue
            for f_ in fields:
                if not isinstance(item.get(f_, ""), str):
                    errs.append(f'"{sec}" item {i}: "{f_}" must be text.')
            b = item.get("bullets")
            if not (isinstance(b, list) and all(isinstance(x, str) for x in b)):
                errs.append(f'"{sec}" item {i}: "bullets" must be a list of text items.')
    return errs


# --------------------------------------------------------------------------
# Keyword analysis
# --------------------------------------------------------------------------
def extract_keywords(text):
    """{keyword: count} for keywords found in text, most frequent first."""
    found = {}
    for name, rx in _RX.items():
        n = len(rx.findall(text or ""))
        if n:
            found[name] = n
    return dict(sorted(found.items(), key=lambda kv: -kv[1]))


def resume_text(r, include_headline=True):
    parts = [r.get("headline", "")] if include_headline else []
    parts += [r.get("summary", "")]
    parts += r.get("skills", [])
    for e in r.get("experience", []):
        parts += [e.get("title", ""), e.get("company", "")] + e.get("bullets", [])
    for p in r.get("projects", []):
        parts += [p.get("title", "")] + p.get("bullets", [])
    parts += r.get("certifications", []) + r.get("education", [])
    return "\n".join(parts)


def _scorer(job_kws):
    def score(text):
        return sum(min(c, 5) for k, c in job_kws.items() if _RX[k].search(text))
    return score


def _join_and(items):
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def adapt_headline(current, job_title):
    if not job_title or SENIOR_RX.search(job_title):
        return current
    for pat, label in HEADLINE_RULES:
        if re.search(pat, job_title, re.I):
            return label
    return current


# --------------------------------------------------------------------------
# Tailoring
# --------------------------------------------------------------------------
def tailor(master, job_title, job_text):
    """Return (tailored_resume, report). The master is never modified."""
    r = copy.deepcopy(master)
    job_kws = extract_keywords(f"{job_title}\n{job_text}")
    # The headline is a target title, not evidence of experience, so it
    # doesn't count toward "supported" keywords.
    base_text = resume_text(master, include_headline=False)
    matched = {k: c for k, c in job_kws.items() if _RX[k].search(base_text)}
    missing = {k: c for k, c in job_kws.items() if k not in matched}
    score = _scorer(job_kws)
    changes = []

    new_headline = adapt_headline(master["headline"], job_title)
    if new_headline != master["headline"]:
        r["headline"] = new_headline
        changes.append(f'Headline changed to "{new_headline}" to match the job title.')

    # Summary: only mention keywords the resume already supports.
    summary = master["summary"]
    extras = [k for k in matched
              if k not in GENERIC and not _RX[k].search(summary)][:4]
    if extras:
        r["summary"] = summary.rstrip() + f" Relevant experience includes {_join_and(extras)}."
        changes.append("Summary: added already-supported keywords: " + ", ".join(extras) + ".")

    # Reorder (stable, so ties keep your original order).
    r["skills"] = sorted(master["skills"], key=lambda s: -score(s))
    for e in r["experience"]:
        e["bullets"] = sorted(e["bullets"], key=lambda b: -score(b))
    for p in r["projects"]:
        p["bullets"] = sorted(p["bullets"], key=lambda b: -score(b))
    r["projects"] = sorted(
        r["projects"], key=lambda p: -score(p["title"] + " " + " ".join(p["bullets"])))
    changes.append("Skills, bullets, and projects reordered so the most relevant come first.")
    changes.append("Job history stays in reverse-chronological order (ATS standard).")

    report = {
        "matched": list(matched.items()),
        "missing": list(missing.items()),
        "changes": changes,
        "job_title": job_title,
    }
    return r, report


def format_report(rep):
    lines = []
    m, x = rep["matched"], rep["missing"]
    lines.append(f"JOB KEYWORDS YOUR RESUME ALREADY SUPPORTS ({len(m)})")
    lines += [f"  [+] {k}  (mentioned {c}x in the job)" for k, c in m] or ["  (none found)"]
    lines.append("")
    lines.append(f"JOB KEYWORDS NOT IN YOUR RESUME ({len(x)})")
    lines += [f"  [ ] {k}  (mentioned {c}x in the job)" for k, c in x[:20]] or ["  (none)"]
    lines.append("")
    lines.append("Only add a missing keyword to your master resume if you really")
    lines.append("have that experience. The app never adds them for you.")
    lines.append("")
    lines.append("CHANGES MADE TO THIS COPY")
    lines += [f"  - {c}" for c in rep["changes"]]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# AI rewrite (optional): a full rewrite by Claude, fenced in by a guard
# --------------------------------------------------------------------------
AI_MODEL = "claude-sonnet-5-5"


def build_prompt(master, job_title, company, job_text):
    """Prompt you can paste into Claude.ai (free) or send through the API."""
    return (
        "You are helping an entry-level job seeker tailor their resume to one job.\n\n"
        "STRICT RULES\n"
        "1. Use ONLY facts that appear in the MASTER RESUME below. Never invent employers, "
        "job titles, dates, tools, certifications, degrees, numbers, or responsibilities.\n"
        "2. Keep every experience entry's title, company and dates EXACTLY as written, with "
        "the same number of entries in the same order. Keep name, contact, certifications "
        "and education EXACTLY as written.\n"
        "3. You MAY rewrite the headline, summary, skills, bullets and project bullets: "
        "reword, reorder, merge, and emphasize what is most relevant to this job. Use the "
        "job posting's wording only where the master resume shows the same skill. The "
        "headline must be an entry-level title the candidate is honestly qualified for.\n"
        "4. Do not claim requirements the candidate does not have. List the job's "
        "requirements that the master resume does NOT support in a \"gaps\" array.\n"
        "5. Strong action verbs, no first person, about one to two pages of content.\n"
        "6. Reply with ONLY one JSON object and no commentary, in exactly the same "
        "structure as the master resume, plus one extra key \"gaps\" (array of strings).\n\n"
        f"JOB TITLE: {job_title or '(not given)'}\n"
        f"COMPANY: {company or '(not given)'}\n\n"
        f"JOB DESCRIPTION:\n{(job_text or '').strip()}\n\n"
        f"MASTER RESUME (JSON):\n{json.dumps(master, indent=2, ensure_ascii=False)}\n"
    )


def parse_ai_response(text):
    """Pull the JSON object out of a reply. Returns (resume_dict, gaps_list)."""
    t = (text or "").strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON found. Paste Claude's full reply, including the { } block.")
    data = json.loads(t[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("The reply was not a JSON object.")
    gaps = data.pop("gaps", [])
    gaps = [str(g) for g in gaps] if isinstance(gaps, list) else []
    return data, gaps


def guard(master, new):
    """Check an AI-written resume against the master.
    Returns (errors, warnings). Errors mean: do not use it."""
    if not isinstance(new, dict):
        return ["The result is not a JSON object."], []
    errors = list(validate_master(new))
    if errors:
        return errors, []
    warnings = []
    for k in ("name", "contact"):
        if new[k] != master[k]:
            errors.append(f'"{k}" was changed.')
    if new["certifications"] != master["certifications"]:
        errors.append("Certifications were changed.")
    if new.get("education", []) != master.get("education", []):
        errors.append("Education was changed.")
    me, ne = master["experience"], new["experience"]
    if len(me) != len(ne):
        errors.append(f"Experience has {len(ne)} entries; your master has {len(me)}.")
    else:
        for a, b in zip(me, ne):
            for f in ("title", "company", "dates"):
                if a.get(f, "") != b.get(f, ""):
                    errors.append(f'Experience "{a.get("title", "?")}": "{f}" was changed '
                                  f'to "{b.get(f, "")}".')
    if len(new["projects"]) > len(master["projects"]):
        errors.append("Extra projects were added.")
    base = extract_keywords(resume_text(master, include_headline=False))
    now = extract_keywords(resume_text(new, include_headline=False))
    added = [k for k in now if k not in base and k not in GENERIC]
    if added:
        warnings.append("Keywords that are NOT in your master resume: " + ", ".join(added) +
                        ". Keep them only if they are true.")
    return errors, warnings


def call_api(prompt, api_key, model=AI_MODEL, timeout=180):
    """Send the prompt to the Anthropic API (needs your own API key)."""
    import urllib.error
    import urllib.request

    body = json.dumps({"model": model, "max_tokens": 8000,
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"API error {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach the API: {e.reason}")
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


# --------------------------------------------------------------------------
# Checks, text preview, PDF
# --------------------------------------------------------------------------
def check_issues(r):
    issues = []
    for e in r.get("experience", []):
        d = e.get("dates", "")
        if "confirm" in d.lower() or "?" in d or not d.strip():
            issues.append(f'Dates for "{e.get("title", "?")}" need fixing: "{d}"')
    if "@" not in r.get("contact", ""):
        issues.append("Contact line has no email address.")
    return issues


def _company_visible(company):
    return bool(company.strip()) and company.strip().lower() != "independent experience"


def _entry_header(e):
    head = e["title"]
    if _company_visible(e.get("company", "")):
        head += f", {e['company']}"
    if e.get("dates", "").strip():
        head += f" | {e['dates']}"
    return head


def render_text(r):
    L = [r["name"].upper(), r["headline"], r["contact"], ""]
    L += ["SUMMARY", r["summary"], ""]
    L += ["SKILLS", ", ".join(r["skills"]), ""]
    L.append("EXPERIENCE")
    for e in r["experience"]:
        L.append(_entry_header(e))
        L += [f"  - {b}" for b in e["bullets"]]
        L.append("")
    if r.get("projects"):
        L.append("PROJECTS")
        for p in r["projects"]:
            L.append(p["title"])
            L += [f"  - {b}" for b in p["bullets"]]
            L.append("")
    if r.get("certifications"):
        L.append("CERTIFICATIONS")
        L += [f"  - {c}" for c in r["certifications"]]
        L.append("")
    if r.get("education"):
        L.append("EDUCATION")
        L += [f"  - {c}" for c in r["education"]]
    return "\n".join(L).rstrip() + "\n"


def safe_filename(name, company, title):
    raw = "_".join(p for p in (name, company, title) if p and p.strip())
    raw = re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_")[:100] or "Resume"
    return raw + ".pdf"


def build_pdf(r, path):
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

    e_ = escape
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=10, leading=13)
    name_s = ParagraphStyle("name", parent=base, fontName="Helvetica-Bold",
                            fontSize=18, leading=22, alignment=TA_CENTER)
    center = ParagraphStyle("center", parent=base, alignment=TA_CENTER)
    head_s = ParagraphStyle("head", parent=base, fontName="Helvetica-Bold",
                            fontSize=11, leading=14, spaceBefore=8, keepWithNext=1)
    entry_s = ParagraphStyle("entry", parent=base, fontName="Helvetica-Bold",
                             spaceBefore=4, keepWithNext=1)
    bullet_s = ParagraphStyle("bullet", parent=base, leftIndent=14, bulletIndent=3,
                              spaceAfter=1)

    def section(title):
        return [Paragraph(title.upper(), head_s),
                HRFlowable(width="100%", thickness=0.6, spaceBefore=1, spaceAfter=4)]

    def bullets(items):
        return [Paragraph(e_(b), bullet_s, bulletText="\u2022") for b in items]

    s = [Paragraph(e_(r["name"]), name_s),
         Paragraph(e_(r["headline"]), center),
         Paragraph(e_(r["contact"]), center)]
    s += section("Summary") + [Paragraph(e_(r["summary"]), base)]
    s += section("Skills") + [Paragraph(e_(", ".join(r["skills"])), base)]
    s += section("Experience")
    for e in r["experience"]:
        s.append(Paragraph(e_(_entry_header(e)), entry_s))
        s += bullets(e["bullets"])
    if r.get("projects"):
        s += section("Projects")
        for p in r["projects"]:
            s.append(Paragraph(e_(p["title"]), entry_s))
            s += bullets(p["bullets"])
    if r.get("certifications"):
        s += section("Certifications") + bullets(r["certifications"])
    if r.get("education"):
        s += section("Education") + bullets(r["education"])

    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75 * inch,
                            rightMargin=0.75 * inch, topMargin=0.6 * inch,
                            bottomMargin=0.6 * inch, title=f'{r["name"]} - Resume',
                            author=r["name"])
    doc.build(s)
    return path
