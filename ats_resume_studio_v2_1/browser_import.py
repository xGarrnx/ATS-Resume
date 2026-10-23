"""
ATS Resume Studio - Browser Import
----------------------------------
Opens a real, visible browser window. YOU browse to the job posting
(sign in, pass any "are you human" checks yourself), then click the
floating blue button in the page. The job text is read from the page
you are looking at and returned to Resume Studio.

Tip: if the import comes back empty, HIGHLIGHT the job description with your
mouse first, then click the blue button. Highlighted text is used exactly.

How the click is detected: the button sets a flag inside the page, and this
program checks for that flag every fraction of a second in every open tab.

Runs in its own process so it doesn't clash with the Tkinter window.
A log is written to ~/.ats_resume_studio/import_log.txt for troubleshooting.
"""
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

DATA_DIR = Path.home() / ".ats_resume_studio"
PROFILE_DIR = DATA_DIR / "browser_profile"
LOG_PATH = DATA_DIR / "import_log.txt"

# Installed in every frame. Only the top frame gets the button. The button
# remembers what you had highlighted at the moment you pressed it.
BUTTON_JS = r"""
(() => {
  if (window.__rsInstalled) return;
  window.__rsInstalled = true;
  window.__rsClicked = false;
  window.__rsSel = '';
  if (window !== window.top) return;   // button only in the top frame
  const make = () => {
    if (document.getElementById('__rs_import_btn')) return;
    if (!document.documentElement) return;
    const b = document.createElement('button');
    b.id = '__rs_import_btn';
    b.type = 'button';
    b.textContent = 'Import this job into Resume Studio';
    b.setAttribute('style',
      'position:fixed !important;bottom:20px !important;right:20px !important;' +
      'z-index:2147483647 !important;padding:14px 18px !important;' +
      'font:600 14px sans-serif !important;background:#1a73e8 !important;' +
      'color:#fff !important;border:0 !important;border-radius:8px !important;' +
      'box-shadow:0 2px 10px rgba(0,0,0,.4) !important;cursor:pointer !important');
    // Keep the highlighted text from being lost when the button is pressed.
    b.addEventListener('mousedown', (ev) => {
      try { window.__rsSel = String(window.getSelection() || ''); } catch (e) {}
      ev.preventDefault();
    }, true);
    b.addEventListener('click', (ev) => {
      ev.preventDefault(); ev.stopPropagation();
      window.__rsClicked = true;
      b.textContent = 'Importing...';
    }, true);
    document.documentElement.appendChild(b);
  };
  make();
  setInterval(make, 700);
})();
"""

# Runs once per frame (the job text may live inside an iframe).
EXTRACT_JS = r"""
() => {
  const ownBtn = document.getElementById('__rs_import_btn');
  if (ownBtn) ownBtn.style.setProperty('display', 'none', 'important');  // keep our button out of the text
  const txt = (el) => (el && el.innerText ? el.innerText.trim() : '');
  const q = (sels) => {
    for (const s of sels) {
      let t = '';
      try { t = txt(document.querySelector(s)); } catch (e) {}
      if (t) return t;
    }
    return '';
  };
  let body = txt(document.body) || txt(document.documentElement);
  if (!body && document.documentElement) {
    const c = document.documentElement.cloneNode(true);
    c.querySelectorAll('script,style,noscript,#__rs_import_btn').forEach(n => n.remove());
    body = (c.textContent || '').replace(/\s+/g, ' ').trim();
  }
  let sel = window.__rsSel || '';
  if (!sel) { try { sel = String(window.getSelection() || ''); } catch (e) {} }
  return {
    title: q(['h1[data-testid="jobsearch-JobInfoHeader-title"]',
              'h1.jobsearch-JobInfoHeader-title', 'h1']),
    company: q(['[data-testid="inlineHeader-companyName"]',
                '[data-company-name="true"]',
                '.jobsearch-CompanyInfoContainer a']),
    jd: q(['#jobDescriptionText',
           '[data-testid="jobsearch-JobComponent-description"]',
           '.jobsearch-JobComponent-description']),
    main: q(['main', 'article']),
    body: body,
    selection: sel.trim(),
    url: location.href
  };
}
"""


def _log(msg):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def _launch(p):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    headless = os.environ.get("RS_HEADLESS") == "1"  # used only for automated tests
    # Prefer the Google Chrome you already have installed; fall back to
    # Playwright's bundled Chromium.
    try:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), channel="chrome", headless=headless, viewport=None)
        _log("launched Chrome")
        return ctx
    except Exception as e:
        _log(f"Chrome launch failed ({e}); trying bundled Chromium")
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=headless, viewport=None)
        _log("launched bundled Chromium")
        return ctx


def _clicked_page(ctx):
    """Return the page whose blue button was clicked, or None."""
    for pg in list(ctx.pages):
        try:
            if pg.evaluate("window.__rsClicked === true"):
                return pg
        except Exception:
            continue  # page navigating or closed
    return None


def _collect(page):
    """Read every frame of the page (main frame first)."""
    outs = []
    for fr in list(page.frames):
        try:
            d = fr.evaluate(EXTRACT_JS)
            d["frame_url"] = fr.url
            outs.append(d)
        except Exception as e:
            _log(f"frame read failed ({fr.url}): {e}")
    return outs


def _pick(outs):
    """Choose the best job text from the per-frame results.
    Priority: text you highlighted > the job description box > biggest text."""
    L = lambda s: len(s or "")
    result = {"title": "", "company": "", "description": "", "url": "", "source": ""}
    if not outs:
        return result
    result["url"] = outs[0].get("url", "")
    for key in ("title", "company"):
        for d in outs:
            if d.get(key):
                result[key] = d[key]
                break

    sel = max(outs, key=lambda d: L(d.get("selection")))
    if L(sel.get("selection")) >= 200:
        result["description"], result["source"] = sel["selection"], "highlighted text"
        return result

    with_jd = [d for d in outs if L(d.get("jd")) >= 50]
    if with_jd:
        best = max(with_jd, key=lambda d: L(d["jd"]))
        result["description"], result["source"] = best["jd"], "job description box"
        return result

    def biggest(d):
        return d["main"] if L(d.get("main")) >= 200 else d.get("body", "")

    best = max(outs, key=lambda d: L(biggest(d)))
    result["description"], result["source"] = biggest(best), "page text"
    return result


def _diagnostics(outs):
    parts = [f'{d.get("frame_url", "?")[:60]} -> body {len(d.get("body", ""))} chars'
             for d in outs]
    return "Frames checked: " + (" | ".join(parts) if parts else "none readable")


def _run(url, timeout_s=1800):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = _launch(p)
        ctx.add_init_script(BUTTON_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            _log(f"goto problem: {e}")
        # Make sure the button is also on the page that is already open.
        for pg in ctx.pages:
            try:
                pg.evaluate(BUTTON_JS)
            except Exception:
                pass

        deadline = time.time() + timeout_s
        hit = None
        while time.time() < deadline:
            if not ctx.pages:
                _log("window closed before import")
                break
            hit = _clicked_page(ctx)
            if hit is not None:
                break
            try:
                ctx.pages[0].wait_for_timeout(300)
            except Exception:
                time.sleep(0.3)

        result = {}
        if hit is not None:
            _log(f"button clicked on {hit.url}")
            try:
                outs = _collect(hit)
                diag = _diagnostics(outs)
                _log(diag)
                result = _pick(outs)
                n = len(result["description"])
                _log(f"picked {n} chars from {result['source']}")
                if n < 200:
                    result = {"error": (
                        f"Could not read the job text ({n} characters).\n\n"
                        "Try this: highlight the whole job description in the browser "
                        "with your mouse, then click the blue button again.\n\n"
                        f"Page: {hit.url[:90]}\n{diag}")}
            except Exception as e:
                result = {"error": f"Could not read the page: {e}"}
        try:
            ctx.close()
        except Exception:
            pass
        return result


def import_job_via_browser(url):
    """Returns a dict with title/company/description, a dict with "error",
    or None if the window was closed without importing."""
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), url],
        capture_output=True, text=True)
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        err = (proc.stderr or "").strip().splitlines()
        return {"error": (err[-1] if err else "The browser window did not start.") +
                f"\n(Log: {LOG_PATH})"}
    try:
        data = json.loads(lines[-1])
    except Exception:
        return {"error": "Unexpected output from the browser helper."}
    if data.get("error"):
        return data
    return data if data.get("description") else None


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://www.indeed.com"
    try:
        print(json.dumps(_run(target)))
    except ImportError:
        print(json.dumps({"error": "Playwright is not installed. Run install_requirements.bat."}))
    except Exception as exc:
        _log(traceback.format_exc())
        print(json.dumps({"error": f"{exc}\n(Log: {LOG_PATH})"}))
