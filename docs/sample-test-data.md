# CareerPilot — Fictional Sample Test Data

This document provides fictional information for testing CareerPilot locally.

All names, companies, and experience details are invented.
Do not use real personal information or confidential resumes.

## 1. Sample Job Application

Company: Northwind Robotics (Demo)
Job Title: Backend Engineer
Status: Saved
Job URL: https://example.com/careers/northwind-backend

Job Description:

Build Python and FastAPI services backed by PostgreSQL.
Experience with Docker and AWS is a plus.

Notes: Fictional application for reproducibility testing.

## 2. Sample Resume

Name: Alex Morgan (Fictional)
Position: Backend Software Engineer

Professional Summary:
Software developer experienced in building backend services,
REST APIs, and database-driven applications.

Technical Skills:
- Python
- FastAPI
- PostgreSQL
- SQL
- Docker
- Git
- REST APIs
- JavaScript

Professional Experience:

Backend Developer — Example Software Labs (Fictional)

- Developed backend services using Python and FastAPI.
- Built REST APIs for internal applications.
- Designed PostgreSQL database queries.
- Used Docker for local development.
- Managed source code using Git.

Education:
Bachelor of Science in Computer Science
Example University (Fictional)

## 3. Resume Matching Test

1. Open CareerPilot locally.
2. Navigate to Resume Matching.
3. Paste the fictional resume from Section 2.
4. Paste the job description from Section 1.
5. Run the matching analysis.
6. Verify that a matching score is displayed.
7. Review the matched and missing skills.

The matching score is a deterministic keyword-based heuristic.
It does not measure actual candidate suitability.

## 4. Resume Library Test

1. Open the Resume Library in local mode.
2. Create a resume named "Alex Morgan — Sample Resume".
3. Paste the fictional resume from Section 2.
4. Save the resume.
5. Select the saved resume for matching.
6. Select the fictional Northwind Robotics job application.
7. Run resume matching.
8. Verify that results are displayed.
9. Refresh the page and confirm the saved resume persists.

The Resume Library is unavailable in public demo mode.

## 5. Application Workflow Test

Using the fictional Northwind Robotics application:

1. Create the application with status Saved.
2. Verify that it appears in the Applications list.
3. Confirm that the dashboard counts update.
4. Change its status to Applied.
5. Add a future interview date and preparation notes.
6. Verify that the interview appears on the dashboard.
7. Refresh the application and verify persistence.

## Safety Notes

- Use fictional data only.
- Do not use real resumes or personal information.
- Do not run these tests against an existing development database
  containing records that must be preserved.
- Use a fresh local environment or an isolated test database.
- Do not run the public demo seed script against the local database.
- No production or Render deployment is required.
