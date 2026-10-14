# CareerPilot — Product Specification

**Project:** CareerPilot  
**Type:** AI-Assisted Job Application Tracking and Career Preparation Platform  
**Version:** 1.0 MVP  
**Course:** AI Dev Tools Zoomcamp 2026 Capstone

## 1. Problem Statement

Job seekers often manage applications across job boards, email, spreadsheets, and personal notes. This makes it difficult to track application progress, organize interview schedules, and identify opportunities that best match their qualifications.

CareerPilot solves this problem by providing a centralized application for managing job applications and comparing resume content with job descriptions.

The application is designed to help job seekers stay organized, monitor application progress, and prepare more effectively for career opportunities.

## 2. Target Users

The primary users are individual job seekers who apply to multiple positions and need a simple way to organize their job search.

## 3. MVP Features

### Feature 1 — Job Application Management

Users can:

- Create a job application.
- View all saved applications.
- Edit application details.
- Delete an application.
- Search and filter applications.

Each application contains:

- Company name
- Job title
- Job description (optional)
- Application date
- Application status
- Job posting URL (optional)
- Notes (optional)

Supported statuses:

- Saved
- Applied
- Interview
- Offer
- Rejected

### Feature 2 — Dashboard

The dashboard displays:

- Total applications
- Applications by status
- Upcoming interviews
- Recently updated applications

Users can navigate from the dashboard to individual application records.

### Feature 3 — Interview Tracking

Users can:

- Record an interview date and time.
- Update interview details.
- Add interview preparation notes.
- View upcoming interviews.

Interview information is associated with an existing job application.

### Feature 4 — Resume-to-Job Matching

Users can paste resume text and a job description into the application.

CareerPilot analyzes the two texts and returns:

- A matching score
- Matching keywords or skills
- Missing keywords or skills
- Suggestions for improving alignment

For the MVP, matching will use a deterministic keyword-based algorithm so it is reproducible, testable, and does not require a paid AI service.

The application will clearly label this result as a heuristic matching score, not an authoritative assessment of candidate suitability.

An optional future enhancement will integrate an external language model to provide more detailed feedback.

## 4. Out of Scope for MVP

The following are excluded from the initial release:

- User registration and login
- Multiple user accounts
- Job board integrations
- Automatic job applications
- Email notifications
- Resume PDF or DOCX parsing
- AI-generated interview questions
- Real-time collaboration
- Mobile applications

These may be added after the capstone.

## 5. Core User Stories

**US-01 — Create Application**

As a job seeker, I want to save an application so that I can track a position I am interested in.

**US-02 — Update Application**

As a job seeker, I want to update the status of an application so that I know where it stands.

**US-03 — View Dashboard**

As a job seeker, I want to see application statistics so that I can understand my job search progress.

**US-04 — Track Interview**

As a job seeker, I want to record an interview date so that I can prepare for upcoming interviews.

**US-05 — Compare Resume**

As a job seeker, I want to compare my resume text with a job description so that I can identify relevant skills and potential gaps.

**US-06 — Search Applications**

As a job seeker, I want to search and filter my applications so that I can quickly find a particular position.

## 6. Acceptance Criteria

### Application Management

- Users can create, retrieve, update, and delete applications.
- Required fields are validated.
- Application records persist after the backend restarts.
- Users can filter applications by status and search by company or job title.

### Dashboard

- Application totals reflect stored records.
- Counts by status are correct.
- Upcoming interviews are displayed in chronological order.

### Interview Tracking

- Interview details can be saved and updated.
- Interview information is linked to the correct application.
- Past interviews are excluded from the upcoming interview list.

### Resume Matching

- Users can submit resume text and a job description.
- The API returns a score from 0 to 100.
- The API returns matched and missing keywords.
- Identical inputs produce identical results.
- Empty inputs return validation errors.
- Resume text is not retained by the matching service.

## 7. Proposed Technology Stack

**Frontend:** React, Vite, JavaScript

**Backend:** Python, FastAPI, Pydantic

**Database:** PostgreSQL with SQLAlchemy

**API Contract:** OpenAPI 3.x

**Testing:** Pytest, Vitest, integration tests

**Containerization:** Docker, Docker Compose

**CI/CD:** GitHub Actions

**Deployment:** Cloud-hosted application with publicly accessible demonstration URL

**Agent Extensions:** Reusable skill, specialized subagent, MCP server, guardrail, custom agent

## 8. Architecture

The application follows a three-layer architecture:

React Frontend → FastAPI Backend → PostgreSQL Database

The frontend communicates with the backend through a centralized API service module.

The backend validates requests, implements business logic, and persists application records.

The OpenAPI specification defines the contract between frontend and backend.

Resume matching runs in the backend and does not require external AI services.

## 9. Security and Privacy

- Use synthetic data for demonstrations and tests.
- Do not commit secrets or credentials.
- Store configuration in environment variables.
- Validate API inputs.
- Do not log resume content.
- Do not persist submitted resume text in the matching service.
- Avoid exposing personal job-search records through a public demonstration deployment.
- Document AI tools, data handling, and security limitations.

Because the MVP does not include authentication, the deployed demonstration must use fictional data and must not be used to store real personal information.

## 10. Definition of Done

The MVP is complete when:

- The frontend and backend are functional.
- PostgreSQL persistence works.
- The OpenAPI contract matches the implementation.
- Core frontend and backend tests pass.
- Integration tests cover key workflows.
- Docker Compose runs the complete application.
- CI/CD runs tests automatically and deploys after successful verification.
- A cloud deployment is demonstrated.
- The agent extension pack is documented.
- Security and audit evidence is included.
- The README explains setup, testing, deployment, and AI-assisted development.
