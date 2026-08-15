"""
============================================================
AI Resume Screening & Job Recommendation System
skill_extractor.py
============================================================
This module is responsible for extracting technical and soft
skills from raw resume text (the text is produced upstream by
resume_parser.py).

It exposes a single class, `SkillExtractor`, which can be
imported directly into app.py:

    from skill_extractor import SkillExtractor

    extractor = SkillExtractor()
    result = extractor.extract_skills(resume_text)

The class uses simple, transparent NLP techniques (lowercasing,
punctuation removal, tokenization, and case-insensitive phrase
matching against a predefined skill database) rather than a
heavy ML model — this keeps the module fast, dependency-light,
and easy to understand/extend for a college/SE-level project.
============================================================
"""

# ------------------------------------------------------------
# 1. IMPORTS
# ------------------------------------------------------------
import re
import string
import logging
from typing import Dict, List, Set


# ------------------------------------------------------------
# 2. LOGGING CONFIGURATION
# ------------------------------------------------------------
# A dedicated logger for this module. Using __name__ means log
# messages will clearly show they came from "skill_extractor".
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# 3. SKILL EXTRACTOR CLASS
# ------------------------------------------------------------
class SkillExtractor:
    """
    Extracts technical and soft skills from resume text by matching
    against a predefined skill database, organized by category.
    """

    def __init__(self) -> None:
        """
        Initialize the SkillExtractor by loading the skill database
        into memory. The database is a dictionary mapping each
        category (e.g. 'Programming Languages') to a list of skills.
        """
        self.skill_database: Dict[str, List[str]] = self.load_skill_database()

        # Build a flat lookup: skill_name (lowercase) -> category.
        # This makes it fast to find which category a matched skill
        # belongs to, without looping through the whole database
        # every time.
        self.skill_to_category: Dict[str, str] = {
            skill.lower(): category
            for category, skills in self.skill_database.items()
            for skill in skills
        }

        logger.info(
            "SkillExtractor initialized with %d skills across %d categories.",
            len(self.skill_to_category),
            len(self.skill_database),
        )

    # --------------------------------------------------------
    # 3.1 SKILL DATABASE
    # --------------------------------------------------------
    @staticmethod
    def load_skill_database() -> Dict[str, List[str]]:
        """
        Load and return the predefined skill database.

        The database is organized by category so that later on we
        can report *which type* of skill was found (e.g. a candidate
        strong in "AI / ML" vs. "Soft Skills").

        Returns:
            Dict[str, List[str]]: category name -> list of skill names.
        """
        skill_database: Dict[str, List[str]] = {
            "Programming Languages": [
                "Python", "Java", "C", "C++", "C#", "JavaScript", "TypeScript",
                "Go", "Kotlin", "PHP", "Ruby", "Swift", "R", "Scala", "Rust",
                "MATLAB", "Perl", "Dart", "Objective-C", "Shell Scripting",
                "Bash", "Assembly",
            ],
            "Web Development": [
                "HTML", "CSS", "Bootstrap", "Tailwind CSS", "React", "Angular",
                "Vue", "Node.js", "Express", "Django", "Flask", "FastAPI",
                "jQuery", "REST API", "GraphQL", "Next.js", "Redux",
                "Webpack", "SASS", "LESS", "WordPress", "Laravel",
                "Spring Boot", "ASP.NET", "Web Development", "API Development",
            ],
            "Databases": [
                "SQL", "MySQL", "PostgreSQL", "MongoDB", "SQLite", "Firebase",
                "Oracle", "Redis", "Cassandra", "MariaDB", "DynamoDB",
                "Elasticsearch", "Neo4j", "Database Design", "NoSQL",
            ],
            "AI / ML": [
                "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch",
                "Scikit-learn", "NLP", "Computer Vision", "OpenCV", "Keras",
                "Neural Networks", "Reinforcement Learning", "XGBoost",
                "Hugging Face", "LangChain", "Generative AI",
                "Natural Language Processing", "Artificial Intelligence",
                "Predictive Modeling", "Feature Engineering", "LLM",
            ],
            "Data Science": [
                "Pandas", "NumPy", "Matplotlib", "Seaborn", "Excel",
                "Power BI", "Tableau", "Data Analysis", "Data Visualization",
                "Statistics", "Data Cleaning", "ETL", "Data Mining",
                "Big Data", "Hadoop", "Spark", "Data Wrangling",
                "Business Intelligence", "Regression Analysis",
            ],
            "Cloud": [
                "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes",
                "Terraform", "Jenkins", "CI/CD", "Heroku", "Serverless",
                "Cloud Computing", "Microservices", "DevOps",
                "Load Balancing", "Cloud Security",
            ],
            "Version Control": [
                "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
            ],
            "Operating Systems": [
                "Windows", "Linux", "Ubuntu", "macOS", "Unix", "CentOS",
                "Fedora", "Debian",
            ],
            "Soft Skills": [
                "Communication", "Leadership", "Teamwork", "Problem Solving",
                "Time Management", "Critical Thinking", "Adaptability",
                "Creativity", "Collaboration", "Decision Making",
                "Conflict Resolution", "Emotional Intelligence",
                "Public Speaking", "Negotiation", "Attention to Detail",
                "Work Ethic", "Multitasking", "Interpersonal Skills",
                "Active Listening", "Self Motivation", "Flexibility",
                "Empathy",
            ],
            "Project Management": [
                "Agile", "Scrum", "Kanban", "Jira", "Trello", "Waterfall",
                "Risk Management", "Stakeholder Management",
                "Project Planning", "Sprint Planning", "Confluence",
            ],
            "Testing / QA": [
                "Unit Testing", "Selenium", "PyTest", "JUnit", "Manual Testing",
                "Automation Testing", "Postman", "Integration Testing",
                "Test Case Design", "Bug Tracking",
            ],
            "Networking / Security": [
                "TCP/IP", "DNS", "Firewall", "VPN", "Network Security",
                "Cybersecurity", "Penetration Testing", "Cryptography",
                "OAuth", "SSL/TLS",
            ],
        }
        return skill_database

    # --------------------------------------------------------
    # 3.2 TEXT PREPROCESSING
    # --------------------------------------------------------
    def preprocess_text(self, text: str) -> str:
        """
        Clean and normalize raw resume text for NLP processing.

        Steps performed:
            1. Convert text to lowercase.
            2. Remove punctuation (except characters that are part
               of common skill names, e.g. '+', '#', '.').
            3. Collapse multiple/extra whitespace into a single space.
            4. Strip leading/trailing whitespace.

        Args:
            text (str): Raw resume text.

        Returns:
            str: Cleaned, normalized text ready for tokenization
                 and matching.
        """
        try:
            if not text:
                return ""

            # Step 1: Lowercase everything for case-insensitive matching.
            cleaned = text.lower()

            # Step 2: Remove punctuation, but KEEP a few symbols that are
            # meaningful inside real skill names (e.g. "c++", "c#", "node.js").
            punctuation_to_remove = "".join(
                ch for ch in string.punctuation if ch not in "+#."
            )
            translation_table = str.maketrans(
                punctuation_to_remove, " " * len(punctuation_to_remove)
            )
            cleaned = cleaned.translate(translation_table)

            # Step 3 & 4: Collapse extra whitespace and trim.
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

            return cleaned

        except Exception as error:
            logger.error("Error while preprocessing text: %s", error)
            return ""

    def _tokenize(self, text: str) -> List[str]:
        """
        Split cleaned text into individual word tokens.

        Args:
            text (str): Preprocessed (cleaned) text.

        Returns:
            List[str]: List of word tokens.
        """
        if not text:
            return []
        return text.split()

    # --------------------------------------------------------
    # 3.3 SKILL EXTRACTION
    # --------------------------------------------------------
    def extract_skills(self, text: str) -> Dict:
        """
        Extract all known skills mentioned in the given resume text.

        Uses case-insensitive whole-word/phrase matching against the
        skill database, so "python" matches "Python" and "power bi"
        matches "Power BI", but "java" does NOT wrongly match inside
        "javascript".

        Args:
            text (str): Raw resume text extracted by resume_parser.py.

        Returns:
            Dict: {
                "total_skills_found": int,
                "detected_skills": List[str]  (sorted alphabetically, no duplicates),
                "categories": Dict[str, List[str]] (detected skills grouped by category),
                "skill_frequency": Dict[str, int] (how many times each skill appears)
            }
        """
        try:
            if not text or not text.strip():
                logger.warning("extract_skills() received empty text.")
                return {
                    "total_skills_found": 0,
                    "detected_skills": [],
                    "categories": {},
                    "skill_frequency": {},
                }

            # Lowercase the raw text for matching. We intentionally do
            # NOT strip '+' / '#' / '.' here (preprocess_text already
            # protects them), so multi-symbol skills like "C++" and
            # "C#" can still be detected accurately.
            normalized_text = text.lower()
            # Normalize whitespace only (keep punctuation intact for matching).
            normalized_text = re.sub(r"\s+", " ", normalized_text).strip()

            detected_skills: Set[str] = set()
            skill_frequency: Dict[str, int] = {}
            categories_found: Dict[str, List[str]] = {}

            # Loop through every known skill and search for it as a
            # standalone phrase (not as a substring of another word).
            for skill_lower, category in self.skill_to_category.items():
                # Build a boundary-safe regex pattern:
                # (?<![a-z0-9]) / (?![a-z0-9]) act like word boundaries
                # but also work correctly around symbols such as '+' and '#'.
                pattern = r"(?<![a-z0-9])" + re.escape(skill_lower) + r"(?![a-z0-9])"
                matches = re.findall(pattern, normalized_text)

                if matches:
                    # Recover the "nice" display name (original casing)
                    # instead of the lowercase lookup key.
                    display_name = self._get_display_name(skill_lower)
                    detected_skills.add(display_name)
                    skill_frequency[display_name] = len(matches)

                    categories_found.setdefault(category, [])
                    if display_name not in categories_found[category]:
                        categories_found[category].append(display_name)

            # Sort detected skills alphabetically (case-insensitive sort).
            sorted_skills = sorted(detected_skills, key=str.lower)

            # Sort skills within each category alphabetically too.
            for category in categories_found:
                categories_found[category] = sorted(
                    categories_found[category], key=str.lower
                )

            logger.info("Extracted %d unique skills from resume text.", len(sorted_skills))

            return {
                "total_skills_found": len(sorted_skills),
                "detected_skills": sorted_skills,
                "categories": categories_found,
                "skill_frequency": skill_frequency,
            }

        except Exception as error:
            logger.error("Error while extracting skills: %s", error)
            return {
                "total_skills_found": 0,
                "detected_skills": [],
                "categories": {},
                "skill_frequency": {},
            }

    def _get_display_name(self, skill_lower: str) -> str:
        """
        Given a lowercase skill key, return its original "display"
        casing as stored in the skill database (e.g. "power bi" -> "Power BI").

        Args:
            skill_lower (str): Lowercase skill name.

        Returns:
            str: Original-cased skill name, or the lowercase input if
                 not found (fallback safety net).
        """
        for skills in self.skill_database.values():
            for skill in skills:
                if skill.lower() == skill_lower:
                    return skill
        return skill_lower

    # --------------------------------------------------------
    # 3.4 MISSING SKILLS
    # --------------------------------------------------------
    def get_missing_skills(
        self, extracted_skills: List[str], required_skills: List[str]
    ) -> List[str]:
        """
        Compare the skills found in a resume against a list of skills
        required for a target job, and return the ones that are missing.

        Args:
            extracted_skills (List[str]): Skills detected in the resume.
            required_skills (List[str]): Skills required for a job role.

        Returns:
            List[str]: Alphabetically sorted list of required skills
                       that were NOT found in the resume.
        """
        try:
            if not required_skills:
                return []

            # Compare in lowercase to keep matching case-insensitive.
            extracted_lower: Set[str] = {skill.lower() for skill in extracted_skills}

            missing = [
                skill for skill in required_skills
                if skill.lower() not in extracted_lower
            ]

            # Remove duplicates while preserving distinctness, then sort.
            missing_unique_sorted = sorted(set(missing), key=str.lower)

            logger.info(
                "%d missing skill(s) identified out of %d required.",
                len(missing_unique_sorted), len(required_skills)
            )

            return missing_unique_sorted

        except Exception as error:
            logger.error("Error while computing missing skills: %s", error)
            return []

    # --------------------------------------------------------
    # 3.5 SKILL STATISTICS
    # --------------------------------------------------------
    def get_skill_statistics(self, extracted_skills: List[str]) -> Dict:
        """
        Generate summary statistics for a list of extracted skills,
        such as how many skills fall into each category.

        Args:
            extracted_skills (List[str]): Skills detected in the resume.

        Returns:
            Dict: {
                "total_skills": int,
                "category_breakdown": Dict[str, int]
                    (count of detected skills per category),
                "category_percentage": Dict[str, float]
                    (percentage share of each category, rounded to 2 dp)
            }
        """
        try:
            if not extracted_skills:
                return {
                    "total_skills": 0,
                    "category_breakdown": {},
                    "category_percentage": {},
                }

            category_breakdown: Dict[str, int] = {}

            for skill in extracted_skills:
                category = self.skill_to_category.get(skill.lower(), "Uncategorized")
                category_breakdown[category] = category_breakdown.get(category, 0) + 1

            total = len(extracted_skills)
            category_percentage = {
                category: round((count / total) * 100, 2)
                for category, count in category_breakdown.items()
            }

            return {
                "total_skills": total,
                "category_breakdown": category_breakdown,
                "category_percentage": category_percentage,
            }

        except Exception as error:
            logger.error("Error while generating skill statistics: %s", error)
            return {
                "total_skills": 0,
                "category_breakdown": {},
                "category_percentage": {},
            }


# ------------------------------------------------------------
# 4. STANDALONE DEMO / TEST BLOCK
# ------------------------------------------------------------
if __name__ == "__main__":
    # This block only runs when the file is executed directly
    # (e.g. `python skill_extractor.py`), NOT when it is imported
    # into app.py. It demonstrates the full workflow using a
    # sample resume text.

    sample_resume_text = """
    John Doe is a Software Engineer with 3 years of experience.
    Proficient in Python, Java, and JavaScript, with hands-on experience
    building web applications using React, Node.js, and Flask.
    Skilled in database design using MySQL, PostgreSQL, and MongoDB.
    Experienced with Machine Learning using Scikit-learn, TensorFlow,
    and Pandas/NumPy for data analysis. Familiar with AWS, Docker, and
    Git/GitHub for version control and deployment. Strong communication,
    teamwork, and problem solving skills, with excellent time management
    and adaptability in fast-paced Agile/Scrum environments.
    """

    print("=" * 60)
    print("SKILL EXTRACTOR — DEMO")
    print("=" * 60)

    extractor = SkillExtractor()

    # --- 1. Extract skills from the sample resume ---
    extraction_result = extractor.extract_skills(sample_resume_text)

    print(f"\nTotal Skills Found: {extraction_result['total_skills_found']}")
    print(f"\nDetected Skills:\n{extraction_result['detected_skills']}")
    print(f"\nSkills by Category:")
    for category, skills in extraction_result["categories"].items():
        print(f"  - {category}: {skills}")
    print(f"\nSkill Frequency:\n{extraction_result['skill_frequency']}")

    # --- 2. Check for missing skills against a sample job requirement ---
    required_job_skills = [
        "Python", "Django", "Kubernetes", "React", "Power BI", "Leadership"
    ]
    missing_skills = extractor.get_missing_skills(
        extraction_result["detected_skills"], required_job_skills
    )
    print(f"\nRequired Skills for Job: {required_job_skills}")
    print(f"Missing Skills: {missing_skills}")

    # --- 3. Generate skill statistics ---
    stats = extractor.get_skill_statistics(extraction_result["detected_skills"])
    print(f"\nSkill Statistics:")
    print(f"  Total Skills: {stats['total_skills']}")
    print(f"  Category Breakdown: {stats['category_breakdown']}")
    print(f"  Category Percentage: {stats['category_percentage']}")

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)