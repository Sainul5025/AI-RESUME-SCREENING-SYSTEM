"""
job_recommender.py
------------------
Job Recommendation Engine for the AI Resume Screening & Job Recommendation System.

This module loads target job postings from a CSV file (`jobs.csv`), matches
extracted candidate skills against job skill requirements, calculates detailed
match metrics, and returns ranked recommendations.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Union

import pandas as pd

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class JobRecommender:
    """
    Recommends matching job roles based on skills extracted from a resume.
    """

    def __init__(self, csv_filepath: str = "jobs.csv") -> None:
        """
        Initialize the JobRecommender class and load jobs from CSV.

        :param csv_filepath: Path to the jobs CSV database file.
        """
        self.csv_filepath: str = csv_filepath
        self.jobs_df: pd.DataFrame = self.load_jobs(self.csv_filepath)
        logger.info("JobRecommender initialized with %d jobs.", len(self.jobs_df))

    def load_jobs(self, filepath: str) -> pd.DataFrame:
        """
        Loads and cleans the jobs database from a CSV file using pandas.

        Handles missing files and required column validation gracefully.

        :param filepath: Path to the CSV file containing job listings.
        :return: Cleaned pandas DataFrame of job listings.
        """
        try:
            path = Path(filepath).expanduser().resolve()
            if not path.exists():
                logger.warning("Jobs CSV file not found at: %s. Returning empty DataFrame.", filepath)
                return pd.DataFrame()

            df = pd.read_csv(str(path))

            # Required columns validation
            required_cols = [
                "job_title", "company", "location", "experience",
                "salary", "required_skills"
            ]
            for col in required_cols:
                if col not in df.columns:
                    logger.warning("Missing required column '%s' in %s.", col, filepath)
                    df[col] = ""

            # Ensure optional apply_link column exists
            if "apply_link" not in df.columns:
                df["apply_link"] = "N/A"

            # Fill NA values to avoid runtime issues
            df.fillna({
                "job_title": "Unknown Title",
                "company": "Unknown Company",
                "location": "Remote / Unspecified",
                "experience": "Not Specified",
                "salary": "Not Disclosed",
                "required_skills": "",
                "apply_link": "#"
            }, inplace=True)

            logger.info("Successfully loaded %d job entries from %s.", len(df), filepath)
            return df

        except Exception as error:
            logger.error("Error loading jobs CSV from %s: %s", filepath, str(error))
            return pd.DataFrame()

    def calculate_match_percentage(
        self, extracted_skills: List[str], required_skills: List[str]
    ) -> Dict[str, Union[float, List[str]]]:
        """
        Compares candidate skills with required job skills and calculates match metrics.

        :param extracted_skills: Skills identified from candidate's resume.
        :param required_skills: Skills required by the target job.
        :return: Dict containing match_percentage, matching_skills, and missing_skills.
        """
        try:
            # Case-insensitive normalization
            candidate_set: Set[str] = {
                s.strip().lower() for s in extracted_skills if s and s.strip()
            }
            required_set: Set[str] = {
                s.strip().lower() for s in required_skills if s and s.strip()
            }

            if not required_set:
                return {
                    "match_percentage": 100.0,
                    "matching_skills": [],
                    "missing_skills": []
                }

            # Map lowercase skills back to original casing display names
            display_map: Dict[str, str] = {
                s.strip().lower(): s.strip() for s in (extracted_skills + required_skills) if s
            }

            matched_lower = candidate_set.intersection(required_set)
            missing_lower = required_set - candidate_set

            match_percentage = round((len(matched_lower) / len(required_set)) * 100.0, 2)

            matching_skills = sorted([display_map.get(s, s) for s in matched_lower], key=str.lower)
            missing_skills = sorted([display_map.get(s, s) for s in missing_lower], key=str.lower)

            return {
                "match_percentage": match_percentage,
                "matching_skills": matching_skills,
                "missing_skills": missing_skills
            }

        except Exception as error:
            logger.error("Error calculating match percentage: %s", str(error))
            return {
                "match_percentage": 0.0,
                "matching_skills": [],
                "missing_skills": required_skills
            }

    def filter_jobs(
        self, min_match_percentage: float = 0.0
    ) -> pd.DataFrame:
        """
        Filters jobs based on a minimum match percentage threshold.

        :param min_match_percentage: Minimum match score threshold (0 - 100).
        :return: Filtered DataFrame.
        """
        try:
            if self.jobs_df.empty or "match_percentage" not in self.jobs_df.columns:
                return pd.DataFrame()

            filtered = self.jobs_df[self.jobs_df["match_percentage"] >= min_match_percentage]
            return filtered

        except Exception as error:
            logger.error("Error filtering jobs: %s", str(error))
            return pd.DataFrame()

    def sort_recommendations(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sorts recommendation results by match_percentage in descending order.

        :param recommendations: Unsorted list of job recommendation dicts.
        :return: Sorted list of recommendation dicts.
        """
        try:
            return sorted(
                recommendations,
                key=lambda x: x.get("match_percentage", 0.0),
                reverse=True
            )
        except Exception as error:
            logger.error("Error sorting recommendations: %s", str(error))
            return recommendations

    def recommend_jobs(
        self, extracted_skills: List[str], top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generates top N job recommendations based on matching skills.

        :param extracted_skills: Candidate skills extracted by skill_extractor.py.
        :param top_n: Number of top job recommendations to return (default: 10).
        :return: List of top N formatted job recommendation dictionaries.
        """
        try:
            if self.jobs_df.empty:
                logger.warning("No job database available to recommend from.")
                return []

            if not extracted_skills:
                logger.warning("No extracted skills provided for job recommendations.")

            recommendations: List[Dict[str, Any]] = []

            for _, row in self.jobs_df.iterrows():
                # Parse comma-separated skills from CSV
                raw_skills = str(row.get("required_skills", ""))
                required_skills_list = [
                    s.strip() for s in raw_skills.split(",") if s.strip()
                ]

                # Match evaluation
                match_results = self.calculate_match_percentage(
                    extracted_skills, required_skills_list
                )

                job_recommendation = {
                    "job_title": str(row.get("job_title", "N/A")),
                    "company": str(row.get("company", "N/A")),
                    "location": str(row.get("location", "N/A")),
                    "experience": str(row.get("experience", "N/A")),
                    "salary": str(row.get("salary", "N/A")),
                    "required_skills": required_skills_list,
                    "matching_skills": match_results["matching_skills"],
                    "missing_skills": match_results["missing_skills"],
                    "match_percentage": match_results["match_percentage"],
                    "recommendation_score": match_results["match_percentage"],
                    "apply_link": str(row.get("apply_link", "#"))
                }

                recommendations.append(job_recommendation)

            # Sort recommendations descending by match score
            sorted_recs = self.sort_recommendations(recommendations)

            # Return Top N recommendations
            top_recommendations = sorted_recs[:top_n]
            logger.info("Generated %d job recommendations.", len(top_recommendations))
            return top_recommendations

        except Exception as error:
            logger.error("Error generating job recommendations: %s", str(error))
            return []


# Standard helper function for functional imports in app.py
def recommend_jobs(extracted_skills: List[str], top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Convenience wrapper function to generate job recommendations.

    :param extracted_skills: List of skills extracted from candidate resume.
    :param top_n: Maximum recommendations to return (default 10).
    :return: List of recommendation objects.
    """
    recommender = JobRecommender()
    return recommender.recommend_jobs(extracted_skills, top_n=top_n)


if __name__ == "__main__":
    print("=" * 60)
    print("       JOB RECOMMENDER MODULE - DEMO TEST RUN")
    print("=" * 60)

    # 1. Create a dummy jobs.csv for demonstration purposes if it doesn't exist
    demo_csv = "jobs.csv"
    if not os.path.exists(demo_csv):
        sample_jobs_data = {
            "job_title": [
                "Python Developer",
                "Machine Learning Engineer",
                "Backend Engineer",
                "Data Scientist",
                "Frontend Developer"
            ],
            "company": [
                "Tech Corp",
                "AI Innovations",
                "Cloud Systems",
                "Data Solutions",
                "Web Crafters"
            ],
            "location": [
                "New York, NY",
                "San Francisco, CA",
                "Remote",
                "Austin, TX",
                "Boston, MA"
            ],
            "experience": [
                "2+ years",
                "3+ years",
                "1+ years",
                "2+ years",
                "3+ years"
            ],
            "salary": [
                "$90,000 - $110,000",
                "$130,000 - $160,000",
                "$85,000 - $105,000",
                "$110,000 - $135,000",
                "$95,000 - $115,000"
            ],
            "required_skills": [
                "Python, Flask, SQL, Docker, Git",
                "Python, Machine Learning, TensorFlow, PyTorch, Docker, REST APIs",
                "Python, Flask, REST APIs, PostgreSQL, Docker",
                "Python, SQL, Pandas, NumPy, Scikit-learn, Tableau",
                "JavaScript, React, HTML, CSS, TypeScript"
            ],
            "apply_link": [
                "https://example.com/apply/1",
                "https://example.com/apply/2",
                "https://example.com/apply/3",
                "https://example.com/apply/4",
                "https://example.com/apply/5"
            ]
        }
        pd.DataFrame(sample_jobs_data).to_csv(demo_csv, index=False)
        print(f"[+] Temporary '{demo_csv}' created for testing.")

    # 2. Sample extracted candidate skills
    candidate_skills = [
        "Python", "Flask", "SQL", "Docker", "REST APIs", "Machine Learning", "Git"
    ]

    print(f"\nCandidate Skills: {candidate_skills}\n")

    # 3. Instantiate Recommender and get Top Recommendations
    recommender = JobRecommender(csv_filepath=demo_csv)
    recommendations = recommender.recommend_jobs(candidate_skills, top_n=10)

    # 4. Display Results
    print(f"Top {len(recommendations)} Job Recommendations:")
    print("-" * 60)

    for idx, job in enumerate(recommendations, 1):
        print(f"\n{idx}. {job['job_title']} @ {job['company']}")
        print(f"   Location       : {job['location']}")
        print(f"   Experience     : {job['experience']}")
        print(f"   Salary         : {job['salary']}")
        print(f"   Match Score    : {job['match_percentage']}%")
        print(f"   Matching Skills: {', '.join(job['matching_skills'])}")
        print(f"   Missing Skills : {', '.join(job['missing_skills']) if job['missing_skills'] else 'None'}")
        print(f"   Apply Link     : {job['apply_link']}")

    print("\n" + "=" * 60)