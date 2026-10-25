ChronoShield

Policy Before Action — A Policy-Driven API Security Layer

ChronoShield is a cybersecurity project that demonstrates how API requests from clients and AI agents can be validated, authorized, and controlled before they are allowed to perform protected operations.

Built around a FastAPI backend and a React + TypeScript frontend, ChronoShield evaluates requests using trusted identity information, server-side resource metadata, and a configurable policy engine.

Team: INVOX
Track: Cybersecurity
Project: ChronoShield

⸻

Table of Contents

* The Idea
* Core Objectives
* How a Request Is Decided
* Architecture
* Key Features
* Policy Engine
* Policy Test Scenarios
* API Endpoints
* Example Request
* Technology Stack
* Project Structure
* Getting Started
* Environment Configuration
* Testing and Verification
* Security Principles
* Current Scope and Limitations
* Roadmap
* Team INVOX
* References

⸻

The Idea

Modern applications increasingly expose APIs to users, connected devices, automated services, and AI agents. Authentication alone does not guarantee that a request should be allowed to access a particular resource or perform a particular action.

ChronoShield introduces a policy-driven security layer between the requester and the protected operation.

Instead of immediately executing a request, the system evaluates:

* Who is making the request?
* Is the requester’s identity trusted?
* What action is being requested?
* Which resource is being targeted?
* Does the requester have permission to access that resource?
* Does the operation require additional approval?

The system then produces a structured authorization decision before execution.

Core principle

Authorization must travel with the resource.

A request should be permitted only when the relevant identity, resource, operation, and security policies allow it.

Core Objectives

1. Policy-first execution: Evaluate authorization before performing protected operations.
2. Trusted identity resolution: Avoid treating arbitrary identity information supplied in a request body as proof of identity.
3. Resource-aware authorization: Resolve resource metadata on the server and use it when evaluating access.
4. Explicit decisions: Return structured outcomes with reason codes that explain why a request was allowed, denied, or held for approval.
5. Fail-closed behavior: Prevent protected execution when authorization cannot be established.
6. Testable security logic: Provide predefined scenarios to demonstrate expected policy behavior.
7. Transparent monitoring: Present request evaluations and security information through a web console.

⸻

How a Request Is Decided

Every protected request follows a controlled sequence.

1. Receive request: The API gateway receives a request from a client or AI agent.
2. Validate input: The backend checks the request structure and required fields.
3. Resolve identity: The backend validates the demo token and resolves the associated identity.
4. Resolve resource: The backend obtains authoritative resource metadata from its server-side resource registry.
5. Evaluate policy: The selected policy engine evaluates the identity, requested action, resource, and applicable restrictions.
6. Determine outcome: The system produces ALLOW, DENY, or APPROVAL_REQUIRED.
7. Enforce the decision: Only an authorized request proceeds to the protected executor. Denied and approval-required requests do not execute the protected operation.
8. Return a structured response: The API returns the decision, reason code, explanatory message, and execution status.

⸻

Architecture

The following diagram illustrates the request flow and the relationship between the policy engine and the protected operation.

flowchart TD
    A["Client / AI Agent"] --> B["FastAPI Security Gateway"]
    B --> C["Request Validation"]
    C --> D["Trusted Identity Resolution"]
    D --> E["Server-Side Resource Resolution"]
    E --> F["Policy Engine Factory"]
    F --> G{"Selected Policy Engine"}
    G -->|DEV_MOCK| H["Development Mock Engine"]
    G -->|REAL| I["Formal Policy Engine"]
    H --> J{"Authorization Decision"}
    I --> J
    J -->|ALLOW| K["Protected Parking Executor"]
    J -->|DENY| L["Block Execution"]
    J -->|APPROVAL_REQUIRED| M["Require Approval"]
    K --> N["Structured API Response"]
    L --> N
    M --> N

Architecture components

Component	Responsibility
FastAPI Security Gateway	Receives and routes API requests
Request Validation	Checks request structure and required fields
Identity Resolution	Resolves trusted identity from the demo authentication token
Resource Resolution	Obtains authoritative resource metadata from the backend
Policy Engine Factory	Selects the configured policy engine
Policy Engine	Evaluates access and determines the authorization outcome
Protected Executor	Performs the permitted parking operation
React Console	Provides the interface for testing and inspecting evaluations

The frontend is a presentation and interaction layer. It does not independently decide whether a protected operation is authorized.

⸻

Key Features

1. Policy-Driven API Security

Every protected operation is evaluated against the applicable authorization rules before execution.

2. Trusted Identity Resolution

The backend resolves identities from configured demo tokens instead of trusting user identity or role fields merely because they appear in a request body.

3. Resource-Aware Access Control

Resource metadata is resolved on the server. For example, a user’s district can be compared with the authoritative district associated with a parking resource.

4. Configurable Policy Engine

A shared policy engine factory selects the implementation used by both policy testing and runtime request evaluation.

5. Structured Authorization Decisions

The API distinguishes between permitted requests, denied requests, and requests that require approval.

6. Explainable Denials

Responses include reason codes and messages to help developers understand why a request was denied.

7. Interactive Security Console

The React console provides:

* Overview of the security system
* Policy testing interface
* Request evaluation tester
* Browser-session audit view
* Read-only approvals placeholder

The browser-session audit view is a demonstration interface, not a durable or server-authoritative audit system.

⸻

Policy Engine

ChronoShield uses a shared factory to select the policy engine based on the CHRONOSHIELD_POLICY_ENGINE environment variable.

Two configurations are supported by the current design.

Configuration	Purpose
DEV_MOCK	Development and demonstration policy evaluation
REAL	Evaluation through the formal policy engine implementation

The factory centralizes engine selection so that the policy testing endpoint and runtime request evaluation use consistent configuration logic.

Authorization outcomes

Decision	Meaning	Protected operation
ALLOW	The request satisfies the applicable authorization rules	May execute
DENY	The request violates an authorization rule	Must not execute
APPROVAL_REQUIRED	The request requires an additional approval step	Must not execute until an approval workflow authorizes it

An APPROVAL_REQUIRED result does not mean that approval has already been granted. The current approval interface is a placeholder and is not connected to a complete approval workflow.

⸻

Policy Test Scenarios

ChronoShield includes six predefined policy test scenarios to demonstrate expected behavior.

No.	Scenario	Expected outcome	Reason
1	North district operator reads a North district parking resource	ALLOW	The request satisfies the applicable policy
2	North district operator targets a South district resource	DENY	DISTRICT_MISMATCH
3	Viewer attempts to reserve a parking spot	DENY	ROLE_NOT_AUTHORIZED
4	Requester attempts to close a zone	APPROVAL_REQUIRED	HIGH_IMPACT_APPROVAL_REQUIRED
5	Request contains an unknown domain	Structured error	UNKNOWN_DOMAIN
6	Request contains an unknown operation	Structured error	UNKNOWN_OPERATION

These scenarios are intended to demonstrate authorization behavior and error handling. Policy tests do not execute or mutate parking operations.

Synthetic parking resources

The demonstration uses the following sample resources:

Resource ID	District	Capacity
park_north_1	North	120
park_north_2	North	200
park_south_1	South	150
park_south_2	South	80

These are synthetic demonstration resources, not live parking infrastructure.

⸻

API Endpoints

The backend exposes the following primary endpoints.

Method	Endpoint	Purpose
GET	/api/v1/health	Checks backend availability
GET	/openapi.json	Returns the generated API schema
POST	/api/v1/policies/test	Runs predefined policy tests
POST	/api/v1/requests/evaluate	Evaluates an individual request

The backend API documentation can also be accessed through FastAPI’s automatically generated documentation interface when the development server is running.

⸻

Example Request

The following example demonstrates a cross-district access attempt.

Request

Endpoint: POST /api/v1/requests/evaluate

Header:

x-auth-token: token_operator_north

JSON body:

{
  "request_id": "demo-cross-district-001",
  "action": {
    "domain": "parking",
    "operation": "read",
    "resource_id": "park_south_1",
    "resource_district_id": "district_north"
  },
  "actor": {
    "user_id": "user_operator_north",
    "role": "operator",
    "district_id": "district_north"
  }
}

Expected security behavior

The backend resolves the authenticated identity and authoritative resource metadata. The operator belongs to the North district, while the target resource belongs to the South district.

The policy engine therefore denies the cross-district request.

A representative response is:

{
  "decision": "deny",
  "reason_code": "DISTRICT_MISMATCH",
  "message": "Identity district 'district_north' does not match resource district 'district_south'",
  "executed": false
}

The response illustrates the intended behavior: the authorization failure is explicit, explainable, and enforced before protected execution.

The exact response structure depends on the implementation and should be verified against the running backend.

⸻

Technology Stack

Layer	Technology	Purpose
Backend	Python	Application logic
API framework	FastAPI	API routing, validation, and request handling
Frontend	React	Interactive user interface
Language	TypeScript	Frontend type safety
Build tooling	Vite	Frontend development and production builds
API contract	OpenAPI	API schema generation
Policy layer	Configurable policy engine	Authorization evaluation
Testing	Project test suite	Policy, API, and application verification
Architecture diagrams	Mermaid	Documentation diagrams rendered from text

⸻

Project Structure

The repository is organized around the backend security layer, frontend console, and tests.

ChronoShield/
├── app/
│   ├── main.py
│   ├── api/
│   ├── schemas/
│   ├── security/
│   └── services/
├── src/
│   ├── landing/
│   ├── console/
│   ├── components/
│   └── styles/
├── tests/
├── public/
├── requirements.txt
├── package.json
├── .env.example
├── vite.config.ts
└── README.md

The exact contents of each directory may evolve as the project develops. The architecture diagram is embedded directly in this README, so no external SVG diagram files are required.

⸻

Getting Started

Prerequisites

Install the following development tools:

* Python
* Node.js and npm
* Git

Run the commands below from the appropriate project directories.

1. Start the backend

Open a terminal at the project root, where app/main.py and requirements.txt are available.

Create and activate a virtual environment.

Windows PowerShell:

py -m venv .venv
.\.venv\Scripts\Activate.ps1

Install the Python dependencies:

python -m pip install --upgrade pip
pip install -r requirements.txt

Select the development policy engine:

$env:CHRONOSHIELD_POLICY_ENGINE = "DEV_MOCK"

Start the FastAPI server:

uvicorn app.main:app --reload --port 8000

The backend should now be available at:

http://127.0.0.1:8000

The health endpoint is:

http://127.0.0.1:8000/api/v1/health

2. Run with the REAL policy engine

Stop the development server if it is running. In the same activated PowerShell environment, set the policy engine to REAL:

$env:CHRONOSHIELD_POLICY_ENGINE = "REAL"
uvicorn app.main:app --reload --port 8000

Use this configuration only when the formal policy engine and its required dependencies are correctly configured.

3. Start the frontend

Open a second terminal at the project root, where package.json is located.

Install the dependencies:

npm install

Create the local environment file from the example.

macOS/Linux:

cp .env.example .env

Windows PowerShell:

Copy-Item .env.example .env

Start the development server:

npm run dev

The frontend is typically available at:

http://localhost:5173

Open the console at:

http://localhost:5173/console

Keep the backend and frontend terminals running while using the application.

⸻

Environment Configuration

The .env.example file contains the frontend configuration.

VITE_API_BASE_URL=/backend
VITE_PROXY_TARGET=http://127.0.0.1:8000
VITE_SPLINE_SCENE=

Variable	Purpose
VITE_API_BASE_URL	Base path used by the frontend for API requests
VITE_PROXY_TARGET	Backend target used by the Vite development proxy
VITE_SPLINE_SCENE	Optional scene configuration for the landing-page visual

The Spline scene setting is optional. The native WebGL hero can run without an external Spline scene.

Backend configuration such as CHRONOSHIELD_POLICY_ENGINE should be set in the backend process environment rather than treated as a frontend secret.

Useful development commands

npm run typecheck
npm run lint
npm run build
npm run preview

If the project includes the API generation script, it can be run with:

npm run gen:api

⸻

Testing and Verification

ChronoShield should be verified across policy behavior, backend execution, and frontend builds.

Recommended checks

* Run the backend test suite.
* Verify the six predefined policy scenarios.
* Test cross-district access denial.
* Verify that unauthorized operations are not executed.
* Confirm that unknown domains and operations produce structured errors.
* Run frontend type checking.
* Run frontend linting.
* Create a production frontend build.
* Verify that the frontend proxy reaches the backend correctly.

Previously recorded results

The project previously recorded the following verification results:

* 318 tests passed under DEV_MOCK and REAL.
* Frontend type checking, linting, and production build completed successfully.
* The policy testing endpoint passed all six predefined scenarios.
* The Vite development proxy was tested.

These are historical results, not a claim that the current code has just been tested. Re-run the checks against the latest version before using these results as a current verification statement.

⸻

Security Principles

Server-Side Authorization

The backend is responsible for authorization decisions. Frontend checks may improve usability, but they cannot replace server-side enforcement.

Trusted Identity

Identity, role, and permissions must be derived from trusted authentication and authorization logic. Fields supplied by a requester are not proof of identity.

Authoritative Resource Metadata

Resource ownership and other security-relevant attributes must be resolved using server-side data rather than blindly accepted from a client.

Policy Before Execution

Protected operations must not execute until the authorization decision permits them.

Fail-Closed Behavior

If identity, resource information, or policy evaluation cannot be established reliably, the system should not allow the protected operation to proceed.

Explainable Decisions

Authorization outcomes should provide structured reason codes and messages to support debugging, review, and auditing.

Separation of Responsibilities

The interface presents results, the backend enforces decisions, and the policy layer evaluates authorization rules.

⸻

Current Scope and Limitations

ChronoShield is a cybersecurity demonstration and an evolving MVP. The current implementation should not be represented as a fully production-ready security platform.

Area	Current scope	Further work
Authentication	Demo-token-based identity resolution	Integrate production-grade JWT or OIDC authentication
Policy evaluation	Configurable mock and formal engine modes	Validate formal policy deployment and configuration
Protected operations	Synthetic parking operations	Add additional protected domains and executors
Approval workflow	Read-only placeholder	Implement approval creation, review, and enforcement
Audit	Browser-session audit view	Add durable, server-side audit records
Data storage	Synthetic demonstration state	Add appropriate persistent storage
Monitoring	Development-oriented visibility	Add operational monitoring and alerting
Rate limiting	Not established as a complete production control	Implement and test rate limits
Secrets	Development configuration	Add production secret management
Deployment	Local development workflow	Add deployment hardening and operational controls

The project demonstrates policy-driven authorization, but production use would require additional authentication, persistence, auditability, monitoring, and deployment safeguards.

⸻

Roadmap

Phase 1 — Harden the Core

* Strengthen request validation.
* Verify default-deny behavior.
* Expand policy regression tests.
* Standardize structured error responses.
* Ensure protected operations remain behind authorization enforcement.

Phase 2 — Production Identity and Audit

* Integrate production identity verification.
* Introduce durable server-side audit records.
* Improve identity and resource traceability.
* Add request correlation and operational diagnostics.

Phase 3 — Approval Workflow

* Implement approval request creation.
* Add reviewer authorization and decision handling.
* Enforce approval status before high-impact execution.
* Record approval and execution history.

Phase 4 — Expand Protected Domains

* Extend the policy model beyond parking.
* Add new resource types and operations.
* Reuse the shared policy engine selection and enforcement layer.
* Add domain-specific policy tests.

Phase 5 — Operational Hardening

* Add rate limiting and abuse protection.
* Improve secret and configuration management.
* Add monitoring and alerting.
* Strengthen deployment security.
* Run broader security and integration tests.

⸻

Team INVOX

Team member	Responsibility
Dilip S	Team Lead
Manish Jindal	Contributor
Sushanth Hegde	Contributor
Ashish P	Backend and Integration Lead

Responsibilities may be refined as the project implementation progresses.

⸻

References

The project draws on established concepts and documentation relating to API security, backend development, and frontend tooling.

* OWASP API Security Project
* FastAPI documentation
* Vite documentation
* OpenAPI specification

These references are listed by name to keep this README free of external hyperlinks.

⸻

Closing Statement

ChronoShield demonstrates a simple but important security principle: a request must be authorized before it can act.

By combining trusted identity resolution, server-side resource metadata, policy evaluation, structured decisions, and controlled execution, ChronoShield provides a foundation for exploring secure APIs and AI-agent access control.

ChronoShield — Authorization must travel with the resource.

Team INVOX · ChronoForge · Cybersecurity
