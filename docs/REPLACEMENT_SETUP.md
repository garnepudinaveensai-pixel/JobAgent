JobAgent replacement files
Replace these files in the existing project:
`app/browser/browser_manager.py`
`app/config.py`
`app/main.py`
`app/cli.py`
`app/core/application_execution_router.py`
`app/core/job_agent_service.py`
`.env.example`
No changes are required to the existing `email_sender.py`; the existing SMTP sender is already capable of attaching the selected PDF. The new `app/main.py` injects a real `EmailSender` into the live outreach pipeline while the execution router still blocks sending unless `--execute` is explicitly supplied.
One-time login/session setup
From the project root:
```powershell
.\.venv\Scripts\python.exe -m app.cli login
```
The browser uses the persistent profile:
```text
data/browser-profile
```
Log into Naukri/Indeed/LinkedIn manually in the opened browser. Complete OTP/CAPTCHA yourself. Press Enter in the terminal when finished.
Future JobAgent runs reuse that browser profile.
Email setup
Copy `.env.example` to `.env` if needed and configure:
```text
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USE_TLS=true
EMAIL_SENDER=yourgmail@gmail.com
EMAIL_PASSWORD=your-gmail-app-password
```
For Gmail, use an App Password rather than your normal account password.
Live automatic run
```powershell
.\.venv\Scripts\python.exe -m app.cli run --keywords "Electrical Engineer" --location "Hyderabad" --min-score 60 --limit 10 --execute --outreach-after-apply
```
`--execute` is the explicit live switch. Without it, the run remains dry-run.
`--outreach-after-apply` makes the agent prepare/send recruiter outreach after a successful application when a suitable legitimate contact is available.
The email attachment is resolved from the same resume/application pipeline. When a tailored application PDF was generated, that tailored PDF is preferred for outreach.
Important behavior
Persistent sessions do not bypass CAPTCHA, OTP or human verification.
If a site requires human action, JobAgent stops that job and records the state.
No recruiter email address is invented when no legitimate contact is found.
Duplicate application/history protections remain in place.