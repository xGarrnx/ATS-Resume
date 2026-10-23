"""ATS Resume Studio - desktop app (Tkinter)."""
import json
import os
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, scrolledtext, ttk

import core

MONO = ("Consolas", 10)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ATS Resume Studio V2.2")
        self.geometry("1360x880")
        self.minsize(1050, 680)
        self.q = queue.Queue()
        self.master_data = core.load_master()   # NOTE: not "self.master" (Tk uses that name)
        self.tailored = None
        self.report = None
        self.job_url = ""
        self._build_ui()
        self._load_master_editor()
        self.after(200, self._poll)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)

        left = ttk.Frame(pw, padding=10)
        pw.add(left, weight=1)
        ttk.Label(left, text="1. Get the job posting",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(left, text="Job URL").pack(anchor="w", pady=(6, 0))
        self.url_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.url_var).pack(fill="x")
        self.import_btn = ttk.Button(left, text="Open Browser and Import",
                                     command=self.on_import)
        self.import_btn.pack(fill="x", pady=(6, 0))
        ttk.Label(left, wraplength=420, foreground="#555",
                  text="A browser window opens. Open the job there (sign in or pass any "
                       "checks yourself), then click the blue button at the bottom right "
                       "of the page. Or skip this and paste the description below."
                  ).pack(anchor="w", pady=4)

        row = ttk.Frame(left)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="Job title").grid(row=0, column=0, sticky="w")
        ttk.Label(row, text="Company").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.title_var, self.company_var = tk.StringVar(), tk.StringVar()
        ttk.Entry(row, textvariable=self.title_var).grid(row=1, column=0, sticky="ew")
        ttk.Entry(row, textvariable=self.company_var).grid(row=1, column=1, sticky="ew", padx=(8, 0))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)

        ttk.Label(left, text="Job description").pack(anchor="w", pady=(6, 0))
        self.job_text = scrolledtext.ScrolledText(left, height=11, wrap="word", font=("Segoe UI", 10))
        self.job_text.pack(fill="both", expand=True)

        ttk.Label(left, text="2. Build the resume",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(8, 0))
        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="Quick Tailor (free, instant)",
                   command=self.on_analyze).pack(side="left", fill="x", expand=True)
        ttk.Button(btns, text="Clear", command=self.on_clear).pack(side="left", padx=(6, 0))

        ai = ttk.LabelFrame(left, text="Full AI rewrite (writes a whole new resume from your master)",
                            padding=8)
        ai.pack(fill="x", pady=(8, 0))
        ttk.Button(ai, text="Copy prompt for Claude.ai (free)",
                   command=self.on_copy_prompt).pack(fill="x")
        ttk.Label(ai, wraplength=400, foreground="#555",
                  text="Paste the prompt into Claude.ai, then paste Claude's reply into the "
                       "'AI Result' tab and click Use This Result."
                  ).pack(anchor="w", pady=(2, 6))
        ttk.Label(ai, text="Or use your Anthropic API key (paid, one click)").pack(anchor="w")
        self.key_var = tk.StringVar(value=os.environ.get("ANTHROPIC_API_KEY", ""))
        ttk.Entry(ai, textvariable=self.key_var, show="*").pack(fill="x")
        self.api_btn = ttk.Button(ai, text="Rewrite with API key", command=self.on_api_rewrite)
        self.api_btn.pack(fill="x", pady=(4, 0))

        right = ttk.Notebook(pw)
        pw.add(right, weight=2)
        self.nb = right

        self.preview = scrolledtext.ScrolledText(right, wrap="word", font=MONO, state="disabled")
        right.add(self.preview, text="Tailored Resume")
        self.keywords = scrolledtext.ScrolledText(right, wrap="word", font=MONO, state="disabled")
        right.add(self.keywords, text="ATS Keywords")

        af = ttk.Frame(right, padding=6)
        right.add(af, text="AI Result")
        abar = ttk.Frame(af)
        abar.pack(fill="x", pady=(0, 6))
        ttk.Button(abar, text="Use This Result", command=self.on_use_ai_result).pack(side="left")
        ttk.Label(abar, foreground="#555",
                  text="Paste Claude's reply here. Employers, dates and certifications are "
                       "checked against your master before it's accepted."
                  ).pack(side="left", padx=8)
        self.ai_text = scrolledtext.ScrolledText(af, wrap="word", font=MONO)
        self.ai_text.pack(fill="both", expand=True)

        mf = ttk.Frame(right, padding=6)
        right.add(mf, text="Master Resume")
        bar = ttk.Frame(mf)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Save Master", command=self.on_save_master).pack(side="left")
        ttk.Button(bar, text="Reload from file", command=self._load_master_editor).pack(side="left", padx=6)
        ttk.Label(bar, foreground="#555",
                  text="Edit your dates and details here. Your master is never changed by tailoring."
                  ).pack(side="left", padx=6)
        self.master_text = scrolledtext.ScrolledText(mf, wrap="none", font=MONO)
        self.master_text.pack(fill="both", expand=True)

        bottom = ttk.Frame(self, padding=(10, 6))
        bottom.pack(fill="x")
        self.status = tk.StringVar(value="Ready. Import a job or paste a description to begin.")
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        ttk.Button(bottom, text="4. Open Apply Page", command=self.on_apply).pack(side="right")
        ttk.Button(bottom, text="Open Output Folder", command=self.on_open_folder).pack(side="right", padx=6)
        ttk.Button(bottom, text="3. Export PDF", command=self.on_export).pack(side="right")

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _set(widget, text, readonly=True):
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled" if readonly else "normal")

    def _load_master_editor(self):
        try:
            self.master_data = core.load_master()
        except Exception as e:
            messagebox.showerror("Master resume", f"Could not read master_resume.json:\n{e}")
            return
        self._set(self.master_text, json.dumps(self.master_data, indent=2, ensure_ascii=False),
                  readonly=False)

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "import":
                    self._on_import_done(payload)
                elif kind == "ai":
                    self._on_api_done(payload)
        except queue.Empty:
            pass
        self.after(200, self._poll)

    def _job_inputs(self):
        """(title, company, text) or None if no usable description yet."""
        text = self.job_text.get("1.0", "end").strip()
        if len(text) < 40:
            messagebox.showinfo("Job description", "Import or paste a job description first.")
            return None
        return self.title_var.get().strip(), self.company_var.get().strip(), text

    def _show_results(self):
        self._set(self.preview, core.render_text(self.tailored))
        self._set(self.keywords, core.format_report(self.report))
        self.nb.select(0)

    # ------------------------------------------------------------ import
    def on_import(self):
        url = self.url_var.get().strip()
        if not url.lower().startswith("http"):
            messagebox.showinfo("Job URL", "Paste a full job link starting with http or https.")
            return
        self.job_url = url
        self.import_btn.config(state="disabled")
        self.status.set("Browser opened. Open the job there, then click the blue button (bottom right of the page).")

        def work():
            try:
                import browser_import
                data = browser_import.import_job_via_browser(url)
            except Exception as e:
                data = {"error": str(e)}
            self.q.put(("import", data))

        threading.Thread(target=work, daemon=True).start()

    def _on_import_done(self, data):
        self.import_btn.config(state="normal")
        self.lift()
        if data is None:
            self.status.set("Import cancelled. You can paste the job description instead.")
            return
        if data.get("error"):
            self.status.set("Import failed.")
            messagebox.showwarning(
                "Import problem",
                f"{data['error']}\n\nYou can still copy the job description from your "
                "browser and paste it into the box.")
            return
        self.title_var.set(data.get("title", ""))
        self.company_var.set(data.get("company", ""))
        if data.get("url"):
            self.job_url = data["url"]
        self.job_text.delete("1.0", "end")
        self.job_text.insert("1.0", data.get("description", ""))
        self.status.set("Job imported. Tailoring...")
        self.on_analyze()

    # ------------------------------------------------------------ quick tailor
    def on_analyze(self):
        inputs = self._job_inputs()
        if not inputs:
            return
        title, _company, text = inputs
        try:
            self.tailored, self.report = core.tailor(self.master_data, title, text)
        except Exception as e:
            messagebox.showerror("Tailoring failed", str(e))
            return
        self._show_results()
        n, m = len(self.report["matched"]), len(self.report["missing"])
        self.status.set(f"Quick-tailored. {n} job keywords matched, {m} not in your resume. "
                        "Review, then export (or try the full AI rewrite).")

    def on_clear(self):
        self.url_var.set("")
        self.title_var.set("")
        self.company_var.set("")
        self.job_url = ""
        self.job_text.delete("1.0", "end")
        self.tailored = self.report = None
        self._set(self.preview, "")
        self._set(self.keywords, "")
        self.status.set("Cleared.")

    # ------------------------------------------------------------ AI rewrite
    def on_copy_prompt(self):
        inputs = self._job_inputs()
        if not inputs:
            return
        prompt = core.build_prompt(self.master_data, *inputs)
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.update()
        self.nb.select(2)
        self.status.set("Prompt copied. Paste it into Claude.ai, then paste the reply here.")
        messagebox.showinfo(
            "Prompt copied",
            "1. Open Claude.ai and paste (Ctrl+V).\n"
            "2. Copy Claude's whole reply.\n"
            "3. Paste it into the AI Result tab here and click Use This Result.")

    def on_api_rewrite(self):
        inputs = self._job_inputs()
        if not inputs:
            return
        key = self.key_var.get().strip()
        if not key:
            messagebox.showinfo("API key", "Enter your Anthropic API key, or use the free "
                                           "copy-prompt option.")
            return
        prompt = core.build_prompt(self.master_data, *inputs)
        self.api_btn.config(state="disabled")
        self.status.set("Asking Claude to rewrite your resume... (up to a minute)")

        def work():
            try:
                self.q.put(("ai", {"text": core.call_api(prompt, key)}))
            except Exception as e:
                self.q.put(("ai", {"error": str(e)}))

        threading.Thread(target=work, daemon=True).start()

    def _on_api_done(self, res):
        self.api_btn.config(state="normal")
        if res.get("error"):
            self.status.set("AI rewrite failed.")
            messagebox.showerror("AI rewrite failed", res["error"])
            return
        self.ai_text.delete("1.0", "end")
        self.ai_text.insert("1.0", res["text"])
        self._use_ai_text(res["text"])

    def on_use_ai_result(self):
        self._use_ai_text(self.ai_text.get("1.0", "end"))

    def _use_ai_text(self, text):
        try:
            new, gaps = core.parse_ai_response(text)
        except ValueError as e:
            messagebox.showerror("Could not read the reply", str(e))
            return
        errors, warnings = core.guard(self.master_data, new)
        if errors:
            messagebox.showerror(
                "Result rejected",
                "This rewrite changes things it isn't allowed to:\n\n- " + "\n- ".join(errors) +
                "\n\nAsk Claude to try again and keep those exactly as written.")
            return
        if warnings and not messagebox.askyesno(
                "Check before using", "\n".join(warnings) + "\n\nUse this rewrite anyway?",
                default="no"):
            return
        inputs = self._job_inputs()
        title, _company, jtext = inputs if inputs else ("", "", "")
        _, rep = core.tailor(self.master_data, title, jtext)   # for the keyword lists only
        rep["changes"] = ["Full rewrite written by Claude from your master resume.",
                          "Read every line and make sure it is true for you."] + \
                         [f"Gap (job wants it, your resume doesn't show it): {g}" for g in gaps] + \
                         [f"Note: {w}" for w in warnings]
        self.tailored, self.report = new, rep
        self._show_results()
        self.status.set("AI rewrite loaded. Read it carefully, then export.")

    # ------------------------------------------------------------ master
    def on_save_master(self):
        try:
            data = json.loads(self.master_text.get("1.0", "end"))
        except json.JSONDecodeError as e:
            messagebox.showerror("Not saved", f"That isn't valid JSON:\n{e}")
            return
        errs = core.validate_master(data)
        if errs:
            messagebox.showerror("Not saved", "\n".join(errs))
            return
        core.save_master(data)
        self.master_data = data
        self.status.set("Master resume saved. Rebuild the tailored copy to use the changes.")

    # ------------------------------------------------------------ export / apply
    def on_export(self):
        if self.tailored is None:
            self.on_analyze()
            if self.tailored is None:
                return
        issues = core.check_issues(self.tailored)
        if issues:
            msg = "Please check before sending this out:\n\n- " + "\n- ".join(issues) + \
                  "\n\nExport anyway?"
            if not messagebox.askyesno("Resume needs attention", msg, default="no"):
                self.nb.select(3)
                return
        core.OUTPUT_DIR.mkdir(exist_ok=True)
        fname = core.safe_filename(self.tailored["name"], self.company_var.get(),
                                   self.title_var.get())
        path = core.OUTPUT_DIR / fname
        try:
            core.build_pdf(self.tailored, path)
        except Exception as e:
            messagebox.showerror("PDF export failed", str(e))
            return
        self.status.set(f"Saved: {path}")
        if hasattr(os, "startfile"):
            try:
                os.startfile(str(path))
            except Exception:
                pass

    def on_open_folder(self):
        core.OUTPUT_DIR.mkdir(exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(core.OUTPUT_DIR))
        else:
            messagebox.showinfo("Output folder", str(core.OUTPUT_DIR))

    def on_apply(self):
        """Open the job page in your normal browser and the PDF folder.
        You review the questions and press Submit yourself."""
        url = self.job_url or self.url_var.get().strip()
        if not url.lower().startswith("http"):
            messagebox.showinfo("Apply", "There's no job link yet. Paste the job URL first.")
            return
        webbrowser.open(url)
        self.on_open_folder()
        self.status.set("Job page opened. Click Apply there and upload your PDF from the output folder.")


if __name__ == "__main__":
    App().mainloop()
