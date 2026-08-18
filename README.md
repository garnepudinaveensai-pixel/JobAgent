JobAgent
JobAgent is an automated job-search and application-assistance system designed to discover relevant jobs, evaluate them against a candidate profile, select and tailor resumes, make application decisions, safely prepare applications, track application history, manage application lifecycle states, and generate application reports.
The system is designed around controlled automation. Potentially irreversible actions such as submitting an application or sending outreach require explicit execution and confirmation rather than happening accidentally.
---
Architecture
```text
Job Sources
    │
    ▼
Job Discovery
    │
    ▼
Job Processing / Parsing
    │
    ▼
Job Matching
    │
    ▼
Job Ranking
    │
    ▼
Resume Selection
    │
    ▼
Application Decision Engine
    │
    ▼
Application Lifecycle + History
    │
    ├── Duplicate prevention
    ├── Retry management
    ├── Closed-job detection
    ├── Human-action states
    └── Application status tracking
    │
    ▼
Application Execution Router
    │
    ├── Browser application
    ├── Email outreach
    ├── Manual review
    └── Skip
    │
    ▼
Safety / Validation
    │
    ▼
Application Result
    │
    ▼
History + Reporting
```
---
Features
1. Job Discovery
JobAgent supports job discovery through configured job sources and site-specific integrations.
Supported source integrations include:
Greenhouse
Indeed
Lever
Naukri
Workday
The source layer is separated from the core application logic so additional job sources can be added without rewriting the entire system.
---
2. Job Matching and Ranking
Discovered jobs are processed and evaluated against the candidate profile.
The matching and ranking pipeline provides:
Job parsing
Candidate/job matching
Skill comparison
Resume selection
Ranking scores
Ranked job results
The application layer consumes ranked results instead of independently deciding whether a job is relevant.
---
3. Resume Management
JobAgent supports:
Resume selection
Resume tailoring
Tailored resume PDF generation
Resume validation
Resume upload during application preparation
The system is designed to work with existing candidate information rather than inventing qualifications or experience.
---
Application System
4. Application Decision Engine
The `ApplicationDecisionEngine` determines the appropriate action for a ranked job.
Possible decisions include:
`apply`
`review`
`skip`
The decision engine is intentionally separated from the execution layer.
This prevents application execution code from independently deciding whether a candidate should apply.
---
5. Application Execution Router
`ApplicationExecutionRouter` converts the decision into an execution path.
```text
APPLY
  │
  ├── Browser Application
  │
  └── Email Outreach

REVIEW
  │
  └── Manual Review

SKIP
  │
  └── No Execution
```
The router also propagates application preparation and safety states.
A failed preparation step is never incorrectly treated as a successful application.
---
6. Application Safety
JobAgent includes safety checks around browser-based applications.
The application layer can detect states such as:
CAPTCHA detected
Login required
Job unavailable
Application form unavailable
Validation failure
Human action required
When human intervention is required, the system stops instead of attempting to bypass the protection.
Example:
```text
CAPTCHA detected
       │
       ▼
Human action required
       │
       ▼
Automation stops
```
CAPTCHA
JobAgent does not attempt to bypass CAPTCHA or other human-verification mechanisms.
Authentication
If a website requires login, the system surfaces the requirement instead of attempting to circumvent authentication.
---
Application History and Lifecycle
7. Application History
`ApplicationHistory` provides persistent JSON-based application tracking.
It records information such as:
Job identity
Application status
Decision
Attempts
Submission state
Outreach state
Human-action requirements
Errors
Timestamps
Job identity is derived deterministically using available job information such as:
Canonical URL
Job ID
Company/title/location information
The history store uses atomic persistence to reduce the risk of corrupting the history file.
---
8. Duplicate Prevention
Application history is checked before application execution.
For example:
```text
Job discovered
     │
     ▼
History lookup
     │
     ├── Already applied ──► Skip
     │
     └── Not applied ──────► Continue
```
This prevents JobAgent from repeatedly submitting applications to the same job.
---
9. Application Lifecycle
`ApplicationLifecycle` determines whether a previously processed job should be:
Executed
Retried
Skipped
Closed
Held for human action
Waited on until a future retry/follow-up time
Examples:
```text
Applied
   │
   ▼
Do not apply again
```
```text
CAPTCHA detected
   │
   ▼
Human action required
```
```text
Submission failed
   │
   ▼
Eligible for retry
```
```text
Job unavailable
   │
   ▼
Closed
```
```text
Validation failure
   │
   ▼
Can be retried after correction
```
---
JobAgent Service
10. JobAgentService
`JobAgentService` is the main orchestration layer for application execution.
It coordinates:
```text
Ranked Job
    │
    ▼
Lifecycle Check
    │
    ▼
Duplicate / Retry Check
    │
    ▼
Decision Engine
    │
    ▼
Execution Router
    │
    ▼
Result Recording
```
The service supports batch execution while continuing to process other jobs when an individual job fails.
---
End-to-End Application Pipeline
11. Application Preparation
The `EndToEndPipeline` connects ranked jobs to application preparation and submission.
Application preparation is deliberately separated from submission.
```text
Prepare
   │
   ▼
Tailor Resume
   │
   ▼
Generate PDF
   │
   ▼
Open Application
   │
   ▼
Fill Known Fields
   │
   ▼
Upload Resume
   │
   ▼
Validate
   │
   ▼
Ready for Submission
```
Preparation does not automatically mean submission.
---
12. Application Submission
Application submission requires explicit confirmation.
This separation prevents accidental applications while:
Developing
Testing
Debugging
Preparing resumes
Validating application forms
---
Email Outreach
13. Email Outreach
JobAgent includes an SMTP-based email sender for outreach.
Features include:
Gmail/SMTP support
Environment-based credentials
Resume attachment
Email validation
Dry-run mode
No password storage in result objects
Explicit send invocation
Credentials should be supplied through environment variables.
Never commit `.env` or real credentials to Git.
---
Reporting
14. Application Reporting
`ApplicationReporter` provides application execution summaries and reporting.
Reports can summarize:
Total jobs processed
Applications
Skipped jobs
Manual reviews
Failed applications
Human-action-required states
Outreach results
Application statuses
Reporting is separated from execution so results can be analyzed without changing application behavior.
---
CLI
15. Command-Line Interface
The CLI provides access to JobAgent functionality.
The runtime integration uses the higher-level service architecture rather than bypassing:
Decision engine
Application history
Lifecycle management
Execution router
Safety handling
The application uses safe defaults.
Live execution requires explicit user intent.
---
Dry Run
16. Dry-Run Mode
Dry-run execution is supported for testing the workflow without performing irreversible actions.
Use dry-run mode when validating:
Job discovery
Matching
Ranking
Decisions
Resume selection
Application routing
Reporting
Lifecycle behavior
Before enabling live execution, verify the generated results carefully.
---
Configuration
17. Environment Configuration
Configuration is handled through the application's configuration layer and environment variables.
Use `.env.example` as the template for required environment variables.
Create a local `.env` file when required.
Do not commit `.env`.
Typical configuration areas include:
Job sources
Resume paths
Tailored resume directory
Application history path
Email/SMTP configuration
Browser configuration
Application behavior
---
Installation
18. Create Virtual Environment
On Windows:
```powershell
python -m venv .venv
```
Activate it:
```powershell
.\.venv\Scripts\Activate.ps1
```
---
19. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```
---
20. Install Playwright Browsers
If browser-based integrations are being used:
```powershell
playwright install
```
---
Testing
21. Run the Full Test Suite
Run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Current project verification:
```text
939 passed
0 failed
```
The test suite covers the major system layers including:
Job discovery
Job parsing
Job matching
Job ranking
Resume selection
Application workflow
End-to-end application execution
Application decision engine
Application execution router
JobAgent service
Application safety
Safety-state propagation
Application reporting
Application history
Application lifecycle
Runtime integration
CLI behavior
---
Safety Principles
22. Controlled Automation
JobAgent follows several important safety principles.
No accidental submission
Application preparation and application submission are separate operations.
Explicit confirmation
Irreversible application actions require explicit confirmation.
CAPTCHA is not bypassed
When CAPTCHA or equivalent human verification is detected, the system stops and records that human intervention is required.
Authentication is not bypassed
Login requirements are surfaced to the user.
Failed applications remain distinguishable
A failed application is not recorded as successfully submitted.
Duplicate applications are prevented
Application history is checked before executing an application again.
Retry states are controlled
Recoverable failures can be retried according to lifecycle rules.
Candidate information is not invented
Resume tailoring operates on available candidate information.
---
Project Structure
23. Repository Structure
```text
JobAgent/
│
├── app/
│   ├── agents/
│   │
│   ├── browser/
│   │   ├── application_form.py
│   │   ├── application_submitter.py
│   │   ├── browser_manager.py
│   │   ├── job_discovery.py
│   │   └── sites/
│   │
│   ├── core/
│   │   ├── agent_runner.py
│   │   ├── application_decision_engine.py
│   │   ├── application_execution_router.py
│   │   ├── application_history.py
│   │   ├── application_lifecycle.py
│   │   ├── application_orchestrator.py
│   │   ├── application_pipeline.py
│   │   ├── application_reporter.py
│   │   ├── application_workflow.py
│   │   ├── end_to_end_pipeline.py
│   │   ├── job_agent.py
│   │   ├── job_agent_service.py
│   │   ├── job_application_engine.py
│   │   ├── job_deduplicator.py
│   │   ├── job_match_pipeline.py
│   │   ├── job_parser.py
│   │   ├── job_pipeline.py
│   │   ├── job_processor.py
│   │   ├── job_ranker.py
│   │   ├── matcher.py
│   │   ├── resume_selector.py
│   │   └── sources/
│   │
│   ├── outreach/
│   │
│   ├── resume/
│   │
│   ├── security/
│   │
│   ├── cli.py
│   ├── config.py
│   └── main.py
│
├── data/
│
├── tests/
│
├── .env.example
├── requirements.txt
└── README.md
```
---
Design Philosophy
24. Layered Architecture
JobAgent separates the system into independent layers:
```text
Discovery
   │
   ▼
Intelligence
   │
   ▼
Decision
   │
   ▼
Lifecycle
   │
   ▼
Execution
   │
   ▼
History
   │
   ▼
Reporting
```
This separation makes individual components easier to test, maintain, and extend.
It also prevents application execution behavior from becoming tightly coupled to job discovery or ranking.
---
Current Status
25. Project Status
The core JobAgent application pipeline is implemented and integrated.
Current automated verification:
```text
939 tests passed
0 tests failed
```
Implemented capabilities include:
Job discovery
Job parsing
Job matching
Job ranking
Resume selection
Resume tailoring
Application decision engine
Application execution router
Browser application safety detection
Safety-state propagation
Application history
Duplicate prevention
Application lifecycle management
Retry management
Closed-job handling
Human-action handling
Email outreach
Application reporting
CLI integration
Dry-run support
Runtime integration
The project is ready for final runtime smoke testing and real-world validation.
---
Development Status
26. Development Verification
Before committing changes, run:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Then check:
```powershell
git diff --check
```
For staged changes:
```powershell
git diff --cached --check
```
The repository should contain no secrets, credentials, `.env` files, virtual environments, or generated personal documents.
---
License
This project is currently maintained as a personal software project.
License terms can be added here when the project is formally licensed for redistribution.