"""
ats_score.py
------------
Module for calculating Applicant Tracking System (ATS) scores for resumes.

This module evaluates a resume based on skill matching, section detection,
word count/length, keyword frequency, and formatting best practices.
"""

import logging
import re
from typing import Dict, List, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ATSScore:
    """
    Evaluates resumes and generates ATS scores, feedback, grades,
    and actionable recommendations based on industry standards.
    """

    # Important resume sections and common variants for detection
    SECTION_KEYWORDS: Dict[str, List[str]] = {
        "Contact Information": ["email", "phone", "linkedin", "github", "address", "contact", "mobile"],
        "Education": ["education", "academic", "university", "college", "degree", "bachelor", "master", "phd", "gpa"],
        "Skills": ["skills", "technical skills", "core competencies", "technologies", "proficiencies", "tools"],
        "Experience": ["experience", "work history", "employment", "professional experience", "internship", "responsibilities"],
        "Projects": ["projects", "personal projects", "academic projects", "key projects"],
        "Certifications": ["certifications", "licenses", "certificates", "certified"],
        "Achievements": ["achievements", "accomplishments", "awards", "honors", "recognition"]
    }

    # Common action verbs that indicate strong formatting/writing style
    ACTION_VERBS: Set[str] = {
        "developed", "designed", "implemented", "managed", "led", "created",
        "optimized", "increased", "decreased", "engineered", "orchestrated",
        "spearheaded", "built", "architected", "automated", "improved", "reduced"
    }

    def __init__(self) -> None:
        """Initialize the ATSScore module."""
        logger.info("ATSScore module initialized successfully.")

    def score_skills(
        self, extracted_skills: List[str], required_skills: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculates score based on matched skills against required job skills.

        Weightage: 40 points maximum.

        :param extracted_skills: List of skills extracted from the candidate's resume.
        :param required_skills: List of required skills from the job description.
        :return: Tuple containing (score out of 40, list of missing skills).
        """
        try:
            if not required_skills:
                logger.warning("Required skills list is empty. Awarding full skill points.")
                return 40.0, []

            # Normalize skills to lowercase for accurate matching
            extracted_set: Set[str] = {s.strip().lower() for s in extracted_skills if s}
            required_set: Set[str] = {s.strip().lower() for s in required_skills if s}

            if not required_set:
                return 40.0, []

            matched_skills: Set[str] = extracted_set.intersection(required_set)
            missing_skills: List[str] = list(required_set - extracted_set)

            match_ratio: float = len(matched_skills) / len(required_set)
            score: float = round(match_ratio * 40.0, 2)

            logger.info("Skills Score: %s/40 (Matched %s of %s)", score, len(matched_skills), len(required_set))
            return score, sorted(missing_skills)

        except Exception as e:
            logger.error("Error in score_skills: %s", str(e))
            return 0.0, required_skills if required_skills else []

    def score_sections(self, resume_text: str) -> Tuple[float, List[str], List[str]]:
        """
        Detects whether the resume contains critical structural sections.

        Weightage: 20 points maximum.

        :param resume_text: Raw or preprocessed text of the resume.
        :return: Tuple containing (score out of 20, detected_sections, missing_sections).
        """
        try:
            if not resume_text or not resume_text.strip():
                return 0.0, [], list(self.SECTION_KEYWORDS.keys())

            text_lower: str = resume_text.lower()
            detected_sections: List[str] = []
            missing_sections: List[str] = []

            for section, keywords in self.SECTION_KEYWORDS.items():
                pattern = r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b'
                if re.search(pattern, text_lower):
                    detected_sections.append(section)
                else:
                    missing_sections.append(section)

            total_sections: int = len(self.SECTION_KEYWORDS)
            score: float = round((len(detected_sections) / total_sections) * 20.0, 2)

            logger.info("Sections Score: %s/20 (Detected %s/%s)", score, len(detected_sections), total_sections)
            return score, detected_sections, missing_sections

        except Exception as e:
            logger.error("Error in score_sections: %s", str(e))
            return 0.0, [], list(self.SECTION_KEYWORDS.keys())

    def score_resume_length(self, resume_text: str) -> Tuple[float, str, int]:
        """
        Evaluates resume length based on word count.

        Weightage: 15 points maximum.

        Categories:
        - Too Short: < 150 words (5 points)
        - Average: 150 - 299 words (10 points)
        - Excellent: 300 - 1000 words (15 points)
        - Too Long: > 1000 words (8 points)

        :param resume_text: Raw text of the resume.
        :return: Tuple containing (score out of 15, length category, word count).
        """
        try:
            if not resume_text or not resume_text.strip():
                return 0.0, "Too Short", 0

            words: List[str] = re.findall(r'\b\w+\b', resume_text)
            word_count: int = len(words)

            if word_count < 150:
                category = "Too Short"
                score = 5.0
            elif 150 <= word_count < 300:
                category = "Average"
                score = 10.0
            elif 300 <= word_count <= 1000:
                category = "Excellent"
                score = 15.0
            else:
                category = "Too Long"
                score = 8.0

            logger.info("Length Score: %s/15 (Word count: %s, Category: %s)", score, word_count, category)
            return score, category, word_count

        except Exception as e:
            logger.error("Error in score_resume_length: %s", str(e))
            return 0.0, "Unknown", 0

    def score_keywords(
        self, resume_text: str, required_skills: List[str]
    ) -> float:
        """
        Evaluates the contextual keyword frequency and density within the resume text.

        Weightage: 15 points maximum.

        :param resume_text: Raw text of the resume.
        :param required_skills: Key domain terms/skills expected in the text.
        :return: Score out of 15.
        """
        try:
            if not resume_text or not required_skills:
                return 0.0

            text_lower: str = resume_text.lower()
            keyword_hits: int = 0

            for skill in required_skills:
                if not skill.strip():
                    continue
                # Match skill as whole phrase or word
                pattern = r'\b' + re.escape(skill.strip().lower()) + r'\b'
                matches = re.findall(pattern, text_lower)
                keyword_hits += len(matches)

            # Score scaling: ideally expects 1.5 to 3 keyword mentions per required skill
            ideal_hits: float = max(len(required_skills) * 1.5, 1.0)
            ratio: float = min(keyword_hits / ideal_hits, 1.0)
            score: float = round(ratio * 15.0, 2)

            logger.info("Keyword Score: %s/15 (Total hits: %s)", score, keyword_hits)
            return score

        except Exception as e:
            logger.error("Error in score_keywords: %s", str(e))
            return 0.0

    def score_formatting_bonus(self, resume_text: str) -> float:
        """
        Evaluates resume quality based on presence of action verbs and email/phone structure.

        Weightage: 10 points maximum.

        :param resume_text: Raw text of the resume.
        :return: Score out of 10.
        """
        try:
            if not resume_text or not resume_text.strip():
                return 0.0

            text_lower: str = resume_text.lower()
            words: Set[str] = set(re.findall(r'\b\w+\b', text_lower))

            # Check action verbs
            verb_matches = self.ACTION_VERBS.intersection(words)
            verb_score = min((len(verb_matches) / 5.0) * 5.0, 5.0)  # Max 5 points for verbs

            # Check structure elements (Email & Phone presence)
            has_email = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', resume_text))
            has_phone = bool(re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', resume_text))

            structure_score = (2.5 if has_email else 0.0) + (2.5 if has_phone else 0.0)
            total_bonus = round(verb_score + structure_score, 2)

            logger.info("Formatting Bonus Score: %s/10", total_bonus)
            return total_bonus

        except Exception as e:
            logger.error("Error in score_formatting_bonus: %s", str(e))
            return 0.0

    def get_grade(self, total_score: float) -> str:
        """
        Maps numerical ATS score to a letter grade.

        :param total_score: Overall ATS score (0 to 100).
        :return: Letter grade string (A+, A, B, C, D).
        """
        if total_score >= 90:
            return "A+"
        elif total_score >= 80:
            return "A"
        elif total_score >= 70:
            return "B"
        elif total_score >= 55:
            return "C"
        else:
            return "D"

    def generate_feedback(
        self,
        score: float,
        missing_skills: List[str],
        missing_sections: List[str],
        length_category: str
    ) -> Dict[str, List[str]]:
        """
        Generates structured strengths, weaknesses, and improvement recommendations.

        :param score: Overall calculated ATS score.
        :param missing_skills: List of required skills missing from the resume.
        :param missing_sections: List of important sections missing from the resume.
        :param length_category: Evaluated resume length category.
        :return: Dictionary containing Strengths, Weaknesses, and Suggestions.
        """
        strengths: List[str] = []
        weaknesses: List[str] = []
        suggestions: List[str] = []

        # Evaluate score tier
        if score >= 80:
            strengths.append("High overall match with job description requirements.")
        elif score < 60:
            weaknesses.append("Overall ATS score is low; resume needs significant alignment.")

        # Skills feedback
        if missing_skills:
            weaknesses.append(f"Missing {len(missing_skills)} required technical/soft skill(s).")
            suggestions.append(f"Add missing key skills: {', '.join(missing_skills[:5])}.")
        else:
            strengths.append("Contains all required skills specified in the job description.")

        # Sections feedback
        if missing_sections:
            weaknesses.append(f"Missing essential resume section(s): {', '.join(missing_sections)}.")
            suggestions.append(f"Add standard section headers: {', '.join(missing_sections)}.")
        else:
            strengths.append("Includes all essential resume sections.")

        # Length feedback
        if length_category == "Excellent":
            strengths.append("Optimal resume length (300 - 1000 words).")
        elif length_category == "Too Short":
            weaknesses.append("Resume content is too brief.")
            suggestions.append("Expand on experience, projects, and achievements to hit at least 300 words.")
        elif length_category == "Too Long":
            weaknesses.append("Resume is too long and may fail quick recruiter scans.")
            suggestions.append("Trim fluff and condense experience descriptions into concise bullet points.")

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggestions": suggestions
        }

    def calculate_score(
        self,
        resume_text: str,
        extracted_skills: List[str],
        required_skills: List[str]
    ) -> Dict[str, Union[float, str, List[str], Dict[str, float]]]:
        """
        Calculates the complete ATS Score and comprehensive diagnostic report.

        :param resume_text: Extracted plain text from the resume.
        :param extracted_skills: Skills identified in the resume by skill_extractor.py.
        :param required_skills: Target job requirements skill list.
        :return: Full results dictionary.
        """
        try:
            logger.info("Starting ATS Score calculation...")

            # Handle empty input case gracefully
            if not resume_text or not resume_text.strip():
                logger.warning("Resume text provided is empty.")
                return {
                    "overall_score": 0.0,
                    "grade": "D",
                    "length_category": "Too Short",
                    "word_count": 0,
                    "breakdown": {
                        "skills": 0.0,
                        "sections": 0.0,
                        "length": 0.0,
                        "keywords": 0.0,
                        "formatting_bonus": 0.0
                    },
                    "detected_sections": [],
                    "missing_sections": list(self.SECTION_KEYWORDS.keys()),
                    "missing_skills": required_skills or [],
                    "strengths": [],
                    "weaknesses": ["The uploaded resume contains no readable text."],
                    "suggestions": ["Ensure your uploaded file is not an empty or scanned image-only PDF."]
                }

            # 1. Score Skills (40 pts)
            skills_score, missing_skills = self.score_skills(extracted_skills, required_skills)

            # 2. Score Sections (20 pts)
            sections_score, detected_secs, missing_secs = self.score_sections(resume_text)

            # 3. Score Resume Length (15 pts)
            length_score, length_cat, word_cnt = self.score_resume_length(resume_text)

            # 4. Score Keyword Density (15 pts)
            keywords_score = self.score_keywords(resume_text, required_skills)

            # 5. Score Formatting Bonus (10 pts)
            bonus_score = self.score_formatting_bonus(resume_text)

            # Calculate Overall Score (0-100)
            overall_score: float = round(
                skills_score + sections_score + length_score + keywords_score + bonus_score, 2
            )
            overall_score = min(overall_score, 100.0)

            # Letter Grade
            grade: str = self.get_grade(overall_score)

            # Feedback generation
            feedback = self.generate_feedback(
                score=overall_score,
                missing_skills=missing_skills,
                missing_sections=missing_secs,
                length_category=length_cat
            )

            results = {
                "overall_score": overall_score,
                "grade": grade,
                "length_category": length_cat,
                "word_count": word_cnt,
                "breakdown": {
                    "skills": skills_score,
                    "sections": sections_score,
                    "length": length_score,
                    "keywords": keywords_score,
                    "formatting_bonus": bonus_score
                },
                "detected_sections": detected_secs,
                "missing_sections": missing_secs,
                "missing_skills": missing_skills,
                "strengths": feedback["strengths"],
                "weaknesses": feedback["weaknesses"],
                "suggestions": feedback["suggestions"]
            }

            logger.info("ATS Calculation completed. Final Score: %s (%s)", overall_score, grade)
            return results

        except Exception as e:
            logger.error("Unexpected error in calculate_score: %s", str(e), exc_info=True)
            return {
                "overall_score": 0.0,
                "grade": "D",
                "error": f"Failed to compute ATS score: {str(e)}"
            }


if __name__ == "__main__":
    # Example Demonstration
    print("=" * 60)
    print("       ATS SCORE CALCULATOR - DEMO TEST RUN")
    print("=" * 60)

    # Sample Resume Text
    sample_resume = """
    John Doe
    Email: john.doe@email.com | Phone: (123) 456-7890 | Location: New York, NY
    LinkedIn: linkedin.com/in/johndoe | GitHub: github.com/johndoe

    OBJECTIVE
    Experienced Software Engineer seeking an AI/ML role to build scalable systems.

    EDUCATION
    Bachelor of Science in Computer Science
    University of Technology - GPA: 3.8/4.0

    SKILLS
    Languages: Python, SQL, JavaScript
    Frameworks & Tools: Flask, TensorFlow, PyTorch, Docker, Git, REST APIs
    Core Competencies: Machine Learning, Data Structures, Problem Solving

    PROFESSIONAL EXPERIENCE
    Software Engineer | Tech Innovations Inc. | 2021 - Present
    - Developed and deployed machine learning microservices using Python and Flask.
    - Optimized SQL queries and reduced database latency by 35%.
    - Implemented automated CI/CD pipelines utilizing Docker and Git.
    - Led a team of 4 junior developers to architect REST APIs.

    PROJECTS
    AI Resume Screening System
    - Designed and engineered a Flask-backed web application to parse resumes.
    - Automated skill extraction using Python regex and NLP models.

    CERTIFICATIONS
    - AWS Certified Developer Associate
    - Deep Learning Specialization - Coursera
    """

    # Extracted Skills from skill_extractor.py
    extracted_skills_sample = [
        "Python", "Flask", "SQL", "JavaScript", "TensorFlow",
        "PyTorch", "Docker", "Git", "REST APIs", "Machine Learning"
    ]

    # Job Description Required Skills
    required_skills_sample = [
        "Python", "Flask", "SQL", "Docker", "REST APIs",
        "Machine Learning", "Kubernetes", "AWS", "Pandas"
    ]

    # Instantiate ATSScore
    ats_calculator = ATSScore()

    # Calculate ATS Score
    output = ats_calculator.calculate_score(
        resume_text=sample_resume,
        extracted_skills=extracted_skills_sample,
        required_skills=required_skills_sample
    )

    # Display Results
    print(f"\nOverall ATS Score : {output['overall_score']} / 100")
    print(f"Grade             : {output['grade']}")
    print(f"Word Count        : {output['word_count']} words ({output['length_category']})")

    print("\n--- Score Breakdown ---")
    for category, score in output["breakdown"].items():
        print(f" - {category.capitalize():<18}: {score}")

    print("\n--- Detected Sections ---")
    print(", ".join(output["detected_sections"]))

    if output["missing_sections"]:
        print("\n--- Missing Sections ---")
        print(", ".join(output["missing_sections"]))

    print("\n--- Missing Skills ---")
    print(", ".join(output["missing_skills"]) if output["missing_skills"] else "None")

    print("\n--- Strengths ---")
    for s in output["strengths"]:
        print(f" [+] {s}")

    print("\n--- Weaknesses ---")
    for w in output["weaknesses"]:
        print(f" [-] {w}")

    print("\n--- Suggestions for Improvement ---")
    for sug in output["suggestions"]:
        print(f" [!] {sug}")

    print("\n" + "=" * 60)