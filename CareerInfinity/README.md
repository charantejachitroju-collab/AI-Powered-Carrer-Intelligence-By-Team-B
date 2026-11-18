# CareerInfinity

CareerInfinity is an AI-powered career workspace with a React dashboard and a
FastAPI backend. Existing PDF/DOCX parsing and weighted best-fit role matching
are reused by the new dashboard.

## Run locally (Windows PowerShell)

```powershell
cd CareerInfinity
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
npm run build
python seed_data.py
python app.py
```

Open `http://127.0.0.1:5000/` to sign in and
`http://127.0.0.1:5000/dashboard` for the application. The dashboard opens on
Resume Analyzer by default. Firebase Authentication remains the existing auth
provider; each API call uses its verified Firebase ID token. The frontend does
not introduce a second JWT login system or bypass existing authentication.

For frontend development, run the API in one terminal and the Vite server in a
second:

```powershell
# Terminal 1
python app.py

# Terminal 2
npm run dev
```

Use the Vite server's `dashboard-app.html` entry during development. If the
backend is running on a non-default port, align the frontend and proxy with the
same port by setting `VITE_API_BASE_URL=http://127.0.0.1:5001` (or start the
backend with `PORT=5000`). Configure CORS to allow that Vite origin. Development
uses hash-based client routing so Vite's API proxy can route API paths without
intercepting page navigation.
Production uses normal `/dashboard/...` URLs and serves its static assets from
FastAPI.

The Firebase web settings in the existing sign-in page are public client
configuration, not server credentials. Restrict its API key and authorized
domains in Firebase/Google Cloud. `FIREBASE_PROJECT_ID` must match that
Firebase app. The API loads settings from a local `.env` file as well as the
process environment. Every person cloning this repository should copy
`.env.example` to their own `.env`; `.env` is ignored by Git and must never be
committed or shared. The app runs without an AI key, but AI interview questions
and feedback need each user to configure their own provider key on the backend.

For OpenAI, set `OPENAI_API_KEY` and use the OpenAI defaults in `.env.example`.
For Groq, set `LLM_API_KEY`, change `LLM_API_URL` to
`https://api.groq.com/openai/v1/chat/completions`, and set `LLM_MODEL` to a
model enabled for that account. The key, URL, and model must belong to the same
provider. Restart `python app.py` after changing `.env`. Never put provider keys
in `VITE_*` variables, frontend code, or GitHub. If multiple people need to use
one shared hosted app, configure the key only in the backend host's secret
settings and add suitable usage limits; do not distribute the key to clients.
Without a key, the interview page explains the required setup and AI question
generation reports a configuration error rather than silently substituting
demo questions.

## Dashboard modules

The responsive React Router sidebar includes these modules in order:

1. Dashboard overview, career journey, role match, and recent activity.
2. My Profile with account and career details.
3. Career Recommendations with computed role compatibility and market data.
4. Job Recommendations for roles, learning resources, credentials, and projects.
5. Learning Path with role-specific stages, course links, proof uploads, and progress.
6. Resume Analyzer with upload, score suggestions, and role matching.
7. Interview Preparation with persisted mock sessions, optional LLM feedback, and reports.
8. Certifications earned by the account and editable credential recommendations.
9. Notifications with per-account alerts, search, filters, sorting, preferences, live job listings, and application tracking.
10. Settings for profile, notification, and theme preferences.

The frontend is in `src/` and uses React, Tailwind CSS, Recharts, Lucide icons,
and React Router. The former `/skills` dashboard URL redirects to Roadmap; the
backend `/skills/gap` endpoint remains available for the legacy skill-gap data.
The Roadmap page uses `roadmaps.json`, and `python check_roadmap_links.py`
checks its resource URLs. Roadmap status and proof are stored per Firebase
user; `migrations/001_user_progress.sql` adds the SQLite progress table.
`npm run build` writes the production dashboard to `dist/`;
FastAPI serves the original sign-in page at `/` and the React app at
`/dashboard`.

## API overview

Existing APIs are retained:

- `POST /api/analyze-resume` — existing resume analysis response.
- `POST /match-roles` — existing role matching; accepts PDF/DOCX and `top_n`.
- `GET/PATCH /api/profile` — existing Firebase-authenticated profile.

The new dashboard endpoints use the same Firebase ID-token verification:

| Endpoint | Purpose |
|---|---|
| `GET /dashboard/summary` | Profile, latest analysis, best-fit role, recent activity |
| `POST /resume/analyze` | Reuses parser/scorer/matcher and saves a private resume version |
| `GET /career/intelligence?role=` | Resume role matches and market catalog |
| `GET /skills/gap?role=` | Role-specific learning steps and prioritized roadmap data |
| `GET /roadmaps` | Grouped role catalog from editable `roadmaps.json` |
| `GET /roadmaps/{role}/progress?weekly_study_hours=` | Stage/resource progress, hours, and estimated finish date |
| `PATCH /progress/{resource_id}` | Update a user's resource status, notes, or credential URL |
| `POST /progress/{resource_id}/proof` | Upload a PDF, PNG, or JPEG completion proof (5 MB maximum) |
| `GET /progress/{resource_id}/proof` | Download the signed-in user's proof file |
| `POST /jobs/analyze` | Compare a job description against the latest resume |
| `POST /interview/start` | Start and persist a mock-interview session |
| `POST /interview/{id}/answer` | Save an answer and return feedback |
| `GET /interview/{id}/report` | Session report and improvement tips |
| `GET /recommendations` | Roles, learning resources, and project ideas |
| `GET /drives?type=&sort=` | Filter and sort placement drives |
| `POST/PATCH/DELETE /drives[/{id}]` | Administrator-only drive CRUD |
| `POST /drives/{id}/apply` | Save interest in a drive for the signed-in user |
| `GET/POST /documents` | List or save resume versions |
| `GET/DELETE /documents/{id}` | Download or delete a resume version |
| `GET /documents/compare?first=&second=` | Compare two resume scores |
| `GET /certificates` | Earned credentials and recommended catalog |
| `GET/PATCH /settings` | User-specific profile and preferences |
| `POST /feedback` | Save authenticated user feedback |
| `GET /notifications` | List the signed-in user's notifications with category/status/search/sort filters and offset pagination |
| `GET /notifications/jobs/provider-status` | Check whether both server-side Adzuna credentials are configured (returns booleans only) |
| `POST /notifications/jobs/refresh` | Fetch current job listings from Adzuna when configured; otherwise use the public eGig feed |
| `POST /notifications/sample-jobs/seed` | Add the signed-in user's 100 role-and-package sample alerts once |
| `POST /notifications/{id}/apply` | Save a job application and its initial Applied status for the signed-in user |
| `PATCH /notifications/{id}/application` | Advance that user's application one step through review, interview, and result |
| `PATCH /notifications/{id}/read`, `POST /notifications/read-all` | Mark one or all of the signed-in user's notifications as read |
| `DELETE /notifications/{id}` | Delete a notification owned by the signed-in user |
| `GET/PATCH /notifications/preferences` | Read and save the signed-in user's notification preferences |

Roadmap progress percentages count completed learning resources. Hours are
summed from the catalog's estimates; the finish date uses the requested weekly
study-hour budget. A resource is shown as proof-backed when it is marked
completed and has a proof URL or uploaded file. Proof is user supplied and is
not independently validated with issuers. Basic roadmap roles intentionally
have one foundation stage and are labeled as preliminary in the UI.

Set `DRIVE_ADMIN_TOKEN` to enable placement-drive writes. Send it as
`X-Admin-Token`; never put the token in browser-delivered frontend code. The
admin form in the dashboard only accepts the token at submission time.

SQLAlchemy models in `models.py` define the user, resume, analysis, interview,
drive, application, document, certificate, settings, and feedback tables. The
API keeps its established synchronous SQLite access patterns and per-user
ownership checks. Uploaded files are stored in the private SQLite database.
Set `CAREERINFINITY_DB_PATH` to an absolute path on persistent storage in a
hosted environment and protect/back up that database.

## Smart job notification center

The current project has **no Supabase client or Supabase project configuration**. Its existing identity is Firebase Authentication and its database is SQLite. Notifications use the existing Firebase-verified API and scope saved records to the verified Firebase UID. Migration `003_notification_job_details.sql` removes old fictional records and stores listing details. The page polls the API every 30 seconds while visible; it does not use Supabase Realtime.

The notification screen merges live listings from Adzuna (when configured), eGig, Arbeitnow, and Remotive. Add `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` to the backend's ignored local `.env` to enable Adzuna; each teammate needs their own credentials. The app key stays on the server. If no live source returns jobs, the page can show the requested **100 sample alerts**, clearly marked as samples. Sample salary ranges are illustrative, not employer offers.

Each live card keeps its provider name and original application URL. Adzuna searches use your configured country and preferred roles/locations; eGig is queried per preferred role; Arbeitnow and Remotive feeds are cached to limit repeated requests. Arbeitnow is primarily EU listings; Remotive focuses on remote jobs and asks integrations to credit Remotive and link through to the original posting. Their coverage and geographic fit therefore vary. See [Adzuna's API docs](https://developer.adzuna.com/docs/search), [eGig's API and usage rules](https://egig.in/developers), [Arbeitnow's API docs](https://www.arbeitnow.com/blog/job-board-api) and [terms](https://www.arbeitnow.com/terms), and [Remotive's API docs](https://github.com/remotive-com/remote-jobs-api).

The existing Job Recommendations page recommends roles, learning resources, and project ideas; it is not a live job feed. Placement drives remain separately managed. The app creates CareerInfinity activity notifications when a resume analysis finishes and when a user saves interest in a drive (which is not an employer application). It does not ingest employer application/interview updates. Email preference is stored, but toggling it does not send email.

`migrations/002_notifications_supabase.sql` is a separate Supabase SQL Editor migration artifact with user-scoped RLS, restrictive read-status updates, indexes, preferences, and Realtime publication membership. It is **not applied or used by this Firebase/SQLite application**. Supabase RLS policies depend on Supabase Auth user UUIDs; connecting them while retaining the current Firebase-only sign-in requires a deliberate identity bridge or migration that preserves per-user security. Do not paste a Supabase service-role key into frontend settings or this repository.

SQLite migration `004_job_applications.sql` stores job applications by Firebase user and notification. Applying a live listing creates an account-scoped status record; the Application updates count and Applications view include these records. Status advances through Applied, In review, Interview, and Result one step at a time.

## Editable market and learning data

- `roles.json` defines the job-role catalog and required/nice-to-have skills.
- `scoring_config.json` controls best-fit scoring weights and result caching.
- `market_data.json` contains editable salary ranges, opportunity counts,
  growth classifications, and annual demand-index samples.
- `certifications.json` contains suggested learning/certification resources.
- `seed_drives.json` contains sample placement-drive entries.

Market figures and seeded placement listings are illustrative placeholders,
not sourced labor statistics or actual openings. The UI labels them as sample
data and returns the market `source` and `last_updated` note. Replace them with
verified figures and a real source before presenting them as factual.

## Role matching and scoring

The scorer can use catalog-description embeddings from
`sentence-transformers/all-MiniLM-L6-v2`. Resume text is embedded per request
and cosine similarity is combined with weighted skills and experience. To
avoid blocking local startup on a large model download, the app uses its built-in
lexical scorer by default. Set `ROLE_EMBEDDING_PRELOAD=true` when the model is
available locally or network downloads are acceptable to warm embeddings in
the background.
Default component weights are 30% semantic similarity, 55% skill overlap, and
15% experience fit. The scorer caches results by resume hash and catalog
version. If the embedding package/model is unavailable, it uses lexical cosine
similarity instead.

If `OPENAI_API_KEY` or `LLM_API_KEY` is configured, an OpenAI-compatible
provider may review up to three role explanations, generate interview prompts,
and score mock-interview answers. Resume text and interview responses are sent
to that provider only when configured. Never use untrusted resume text as
instructions; the role-matching prompt treats it as data.

## Architecture

```mermaid
flowchart LR
    Browser[React + Tailwind dashboard] -->|Firebase ID token| API[FastAPI]
    API --> Parser[Existing PDF/DOCX parser]
    Parser --> Analyzer[Existing resume analyzer]
    Parser --> Matcher[Existing weighted role matcher]
    Matcher --> Catalog[roles.json + scoring_config.json]
    API --> Models[SQLAlchemy schema models]
    Models --> DB[(SQLite per-user data)]
    API --> Market[market_data.json]
    API --> Learning[certifications.json]
    API -. configured only .-> LLM[Optional LLM provider]
    API --> Browser
```

## Screenshots

The illustrations below are sample dashboard mockups, not user data. The live
screens show authenticated account data.

![Resume Analyzer and score](./screenshots/best-fit-roles.svg)
![Dashboard module navigation and page previews](./screenshots/dashboard-pages.svg)

## Seed data

```powershell
python seed_data.py
```

This inserts clearly marked, future-dated sample drives and is safe to rerun.
Market data and certification recommendations are loaded from their JSON
catalogs. It deliberately does not create a demo login: authentication remains
bound to the configured Firebase project.

## Tests and evaluation

```powershell
npm test
python -m unittest discover -s . -p "*test.py" -v
python evaluate_role_matching.py
python evaluate_role_matching.py --skip-semantic
```

The role-ranking evaluation uses 20 synthetic labeled resumes. The measured
scores are a smoke test of these examples, not evidence of real-world hiring
accuracy. Tests cover resume parsing, role scoring, persistence, auth guards,
documents, drive administration, settings, and interview flows.

## Docker

```powershell
docker compose up --build
```

The multi-stage image builds the React app and runs FastAPI on port 5000.
SQLite is persisted in the `career_data` volume. Set
`FIREBASE_PROJECT_ID`, `DRIVE_ADMIN_TOKEN`, and optional LLM environment
variables through a protected deployment environment.

## Limitations

Resume and role scores are estimates, not hiring decisions. Keyword skill
signals do not verify proficiency; experience is estimated from explicit
years-of-experience text; scanned PDFs need OCR. Sample market and drive data
must be replaced with sourced, current information. Certificate rows are
account-scoped and remain empty until a trusted assessment/certificate issuer
records a verified credential. An LLM provider is optional and its generated
content can be inaccurate; review it before relying on it.
