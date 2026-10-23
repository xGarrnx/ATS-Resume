ATS RESUME STUDIO V2.2
======================

SETUP (once)
1. Install Python from python.org (tick "Add Python to PATH").
2. Double-click install_requirements.bat
3. Double-click run_windows.bat

USING IT
1. Paste a job link and click "Open Browser and Import". A real browser window
   opens. Open the job (sign in / pass any checks yourself), then click the blue
   "Import this job into Resume Studio" button at the bottom right of the page.
   The button says "Importing..." and the app fills in the job.
   Or just paste the job description into the big box.
   If import fails, see the log: C:\Users\<you>\.ats_resume_studio\import_log.txt
2. Build the resume, either way:
   - Quick Tailor: free and instant. Reorders your master and adds keywords you
     already support.
   - Full AI rewrite: writes a whole new resume from your master.
       a) Free: "Copy prompt for Claude.ai", paste it into Claude.ai, copy the
          reply into the "AI Result" tab, click Use This Result.
       b) Paid: enter your Anthropic API key and click "Rewrite with API key".
     The app REJECTS a rewrite that changes your employers, titles, dates,
     certifications, education or contact info, and warns about any new skills
     that aren't in your master.
3. Read the result and the ATS Keywords tab (gaps = things the job wants that
   your resume doesn't show).
4. Export PDF. Files go in the "output" folder.
5. "Open Apply Page" opens the job in your normal browser and the PDF folder.
   You click Apply, upload the PDF, answer the questions, and submit yourself.

BEFORE YOU APPLY ANYWHERE
- Open the "Master Resume" tab and fix the Independent IT Support dates. The
  field currently says "(confirm dates before using)" and the app will warn you
  until you replace it with dates that are true.
- Your master says A+ Core 1 passed, Core 2 in progress. Update it if that changes.
- Read every line of an AI rewrite. You are the one answering interview questions.

WHY IT DOESN'T SUBMIT APPLICATIONS FOR YOU
Indeed's terms prohibit automated applying, and bots get accounts flagged. The
forms also ask questions only you should answer (work authorization, pay,
availability). Everything up to the Submit button is done for you.

YOUR DATA
- master_resume.json is your master. Tailoring works on a copy.
- Browser sign-ins are stored in your user folder (.ats_resume_studio), not here.
- Your API key is never saved to disk by the app.
