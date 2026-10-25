
import re
from backend.app.observability import tracer


SKILLS = [
    "python",
    "java",
    "javascript",
    "react",
    "fastapi",
    "django",
    "sql",
    "postgresql",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "git",
    "linux",
    "terraform",
    "ci/cd",
    "machine learning",
    "data analysis",
    "networking",
    "5g",
    "cloud computing",
]


def extract_skills(text: str) -> set[str]:
    """Find recognized technical skills in text."""
    text = text.lower()
    found = set()

    for skill in SKILLS:
        pattern = (
            r"(?<!\w)"
            + re.escape(skill)
            + r"(?!\w)"
        )

        if re.search(pattern, text):
            found.add(skill)

    return found


def match_resume(
    resume_text: str,
    job_description: str,
) -> dict:
    """Compare resume skills against job requirements."""

    with tracer.start_as_current_span("resume.match"):
        resume_skills = extract_skills(resume_text)
        required_skills = extract_skills(job_description)

        matched = sorted(resume_skills & required_skills)
        missing = sorted(required_skills - resume_skills)

        if required_skills:
            score = round(
                len(matched) / len(required_skills) * 100
            )
        else:
            score = 0

        suggestions = [
            f"Highlight relevant experience with {skill} if you have it."
            for skill in missing
        ]

        if not required_skills:
            suggestions.append(
                "No recognized technical skills were found in the job description."
            )
        elif not missing:
            suggestions.append(
                "Your resume mentions all recognized skills in the job description."
            )

        return {
            "score": score,
            "matched_keywords": matched,
            "missing_keywords": missing,
            "suggestions": suggestions,
        }
