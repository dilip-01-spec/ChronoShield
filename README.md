# ChronoShield 🛡️

**A cybersecurity gateway for smart-city infrastructure.**

ChronoShield is a full-stack cybersecurity prototype that evaluates requests to smart-city services before allowing protected operations to execute. It combines a React and TypeScript frontend with a FastAPI backend to demonstrate authorization policies, role-based access control, district isolation, and security auditing.

> **Status:** Hackathon prototype — not production-ready.

## Features

- **Policy enforcement:** ALLOW, DENY, and APPROVAL_REQUIRED decisions.
- **Role-based access control:** Demonstrates admin, operator, and viewer permissions.
- **District isolation:** Restricts operators to authorized districts.
- **Server-side identity resolution:** Prevents trusting client-supplied roles as proof of identity.
- **Execution gating:** Demonstrates protected parking operations.
- **Policy testing:** Runs automated policy test scenarios.
- **Security console:** Interactive interface for requests, verdicts, policy tests, and audit history.

## Technology Stack

**Frontend:** React, TypeScript, Vite, Tailwind-free custom CSS, Framer Motion, GSAP, Three.js.

**Backend:** Python, FastAPI, Uvicorn, Pytest, HTTPX.

## Architecture

```text
React + TypeScript Frontend
          |
          v
      FastAPI Gateway
          |
          +--> Identity Resolution
          +--> Policy Engine Adapter
          +--> Authorization Decision
          +--> Protected Parking Service
          +--> Audit Service
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js and npm
- Git

### 1. Clone the repository

```bash
git clone <https://github.com/dilip-01-spec/ChronoShield.git>
cd ChronoShield
```

Replace the placeholder URL with your actual repository URL.

### 2. Start the backend

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start the API:

```bash
CHRONOSHIELD_POLICY_ENGINE=DEV_MOCK python -m uvicorn app.main:app --reload
```

On Windows PowerShell, set the environment variable first:

```powershell
$env:CHRONOSHIELD_POLICY_ENGINE = "DEV_MOCK"
python -m uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

### 3. Start the frontend

Open a second terminal in the project directory:

```bash
npm install
cp .env.example .env
npm run dev
```

Open the local URL printed by Vite, usually `http://localhost:5173`. Keep the backend running while using the frontend.

## API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | API welcome response |
| `GET /api/v1/health` | Health check |
| `POST /api/v1/requests/evaluate` | Evaluate a gateway request |
| `POST /api/v1/policies/test` | Run policy tests |
| `GET /docs` | Swagger API documentation |
| `GET /redoc` | ReDoc API documentation |

## Demo Credentials

The development environment contains synthetic demo tokens:

| Token | Role | District |
|---|---|---|
| `token_admin` | Admin | `district_central` |
| `token_operator_north` | Operator | `district_north` |
| `token_operator_south` | Operator | `district_south` |
| `token_viewer` | Viewer | `district_central` |

Use these tokens only for local testing. They are not production credentials.

## Tests and Build

Run the backend tests:

```bash
python -m pytest -q
```

Build the frontend:

```bash
npm run build
```

Check frontend linting:

```bash
npm run lint
```

**Last local verification:** 318 backend tests passed, and the frontend production build succeeded. The lint command reported warnings that remain to be reviewed.

## Current Limitations

- The development policy engine uses mock rules; the real policy-engine integration is not implemented.
- Demo credentials and audit events are stored in memory.
- The frontend audit view shows browser-session history; authoritative backend audit retrieval is not integrated into the UI.
- The approval manager is not fully integrated with the API and frontend approval queue.
- Only parking operations are currently dispatched through the gateway for execution; other domains are primarily used for policy evaluation.
- The policy testing endpoint is unauthenticated and requires protection before production use.

## Security Notice

ChronoShield is an educational and hackathon prototype. Production deployment would require a trusted identity provider, persistent and protected audit storage, secured administrative endpoints, real policy-engine integration, and comprehensive security testing.

## Contributing

Team members are welcome to contribute. Coordinate changes with the repository owner and use pull requests to review changes.

## License

No license has been selected yet. Public visibility alone does not grant permission to reuse, modify, or redistribute this code.
