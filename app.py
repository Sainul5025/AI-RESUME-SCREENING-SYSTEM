"""
AI Resume Screening & Job Recommendation System - Flask Backend
----------------------------------------------------------------
This file serves as the main Flask application entry point. It imports
and integrates the backend modules (ResumeParser, SkillExtractor, ATSScore,
JobRecommender, and Database) to provide end-to-end resume processing,
analysis, scoring, recommendations, and persistence.

AUTHENTICATION -- PLAN B (simple bearer tokens, no Flask sessions)
--------------------------------------------------------------------
Earlier versions of this file used Flask's built-in cookie-based
session. That turned out to be the root cause of resume uploads
returning 401 Unauthorized even right after a successful login:
Flask's debug reloader regenerates the session-signing secret key on
every restart, invalidating live sessions, and the SameSite/host
rules around cookies are easy to trip up when the frontend is static
HTML served separately from the Flask API.

This version removes cookies/sessions entirely:
    1. POST /login verifies the password and returns a random opaque
       token in the JSON body (see database.py's create_token()).
    2. The frontend (auth.js) stores that token in localStorage and
       resends it on every protected request as:
           Authorization: Bearer <token>
    3. The @token_required decorator below reads that header and
       resolves it straight from the Tokens table -- no cookies, no
       CORS credential flags, no secret-key rotation to worry about.

Every existing feature (upload, parsing, skill extraction, ATS
scoring, job recommendations, and the SQLite persistence layer)
is unchanged.
"""

import os
import re
import logging
from datetime import datetime
from functools import wraps

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

from flask import Flask, request, jsonify
from flask_cors import CORS

# Backend module imports
from resume_parser import ResumeParser
from skill_extractor import SkillExtractor
from ats_score import ATSScore
from job_recommender import JobRecommender
from database import Database

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application Configuration & Global Services
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB limit

# Simple email format validation used for signup.
EMAIL_REGEX = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')

app = Flask(__name__)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
# Plan B does NOT use cookies, so there is no need for
# `supports_credentials=True` and none of the SameSite/credentialed-CORS
# rules that broke the previous session-based flow apply here. The
# Authorization header is just a normal (non-credentialed) request
# header from the browser's point of view.
CORS(app)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize service instances
parser = ResumeParser()
skill_extractor = SkillExtractor()
ats_scorer = ATSScore()
recommender = JobRecommender(csv_filepath=os.path.join(BASE_DIR, "jobs.csv"))
db = Database(db_name=os.path.join(BASE_DIR, "resume.db"))


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def allowed_file(filename: str) -> bool:
    """Check whether the uploaded file has an allowed extension (.pdf, .docx)."""
    if not filename or "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def build_unique_filename(original_filename: str) -> str:
    """Build a safe, timestamped unique filename to avoid overwriting existing uploads."""
    safe_name = secure_filename(original_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{safe_name}"


def extract_applicant_info(resume_text: str, filename: str) -> dict:
    """
    Extract candidate personal information (full name, email, phone) from resume text.
    Falls back to safe defaults if details are not found.
    """
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', resume_text)
    email = email_match.group(0) if email_match else ""

    phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', resume_text)
    phone = phone_match.group(0) if phone_match else ""

    # Simple heuristic to guess candidate name from the first non-empty line
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    full_name = "Unknown Candidate"
    if lines:
        first_line = lines[0]
        if len(first_line.split()) <= 4 and not re.search(r'@|http|www|\d', first_line):
            full_name = first_line

    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "resume_filename": filename
    }


def is_valid_email(email: str) -> bool:
    """Return True if the given string looks like a valid email address."""
    return bool(email) and bool(EMAIL_REGEX.match(email.strip()))


def public_user(user: dict) -> dict:
    """
    Strip sensitive fields (the hashed password) from a user record
    before it is ever included in a JSON response.
    """
    return {
        "id": user.get("id"),
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "created_at": user.get("created_at"),
    }


def get_bearer_token() -> str:
    """
    Extract the bearer token from the request's Authorization header.

    Expects the header in the form:
        Authorization: Bearer <token>

    Returns:
        The token string, or "" if the header is missing/malformed.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    return auth_header[len("Bearer "):].strip()


# ---------------------------------------------------------------------------
# Authentication Decorator (Plan B: bearer token, no Flask session)
# ---------------------------------------------------------------------------
def token_required(view_func):
    """
    Route decorator that restricts access to authenticated users only.

    Reads the "Authorization: Bearer <token>" header, resolves it via
    db.get_user_by_token(), and attaches the result to
    `request.current_user` for the wrapped view to use if needed.

    Responds with HTTP 401 Unauthorized (JSON body) if the header is
    missing or the token doesn't resolve to a valid, still-active
    login -- instead of running the wrapped view.
    """
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        token = get_bearer_token()

        if not token:
            logger.warning(
                "Unauthorized access attempt to '%s': no bearer token supplied.",
                request.path
            )
            return jsonify({
                "success": False,
                "message": "Authentication required. Please log in to continue."
            }), 401

        user = db.get_user_by_token(token)
        if user is None:
            logger.warning(
                "Unauthorized access attempt to '%s': token invalid or expired.",
                request.path
            )
            return jsonify({
                "success": False,
                "message": "Your session has expired. Please log in again."
            }), 401

        # Make the authenticated user available to the view function.
        request.current_user = user
        return view_func(*args, **kwargs)

    return wrapped_view


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.errorhandler(413)
def request_entity_too_large(error):
    """Return JSON error when the uploaded file exceeds 10 MB."""
    logger.warning("File upload rejected: Maximum allowed size (10 MB) exceeded.")
    return jsonify({
        "success": False,
        "message": "File too large. Maximum allowed size is 10 MB."
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Return JSON for unknown routes."""
    return jsonify({
        "success": False,
        "message": "The requested endpoint was not found."
    }), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Return JSON for unexpected server errors."""
    logger.error("Unhandled internal server error: %s", str(error), exc_info=True)
    return jsonify({
        "success": False,
        "message": "An internal server error occurred."
    }), 500


# ---------------------------------------------------------------------------
# Routes - Health Check
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """Health-check route to confirm the backend is running."""
    return jsonify({
        "success": True,
        "message": "Backend Running Successfully"
    })


# ---------------------------------------------------------------------------
# Routes - Authentication (Plan B: bearer tokens)
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["POST"])
def signup():
    """
    Register a new user account.

    Expects JSON body:
        {
            "full_name": "John Doe",
            "email": "john@example.com",
            "password": "password123"
        }

    Validates the input, rejects duplicate emails, hashes the password
    with werkzeug's generate_password_hash, and stores the new user
    in the Users table. Does NOT log the user in automatically --
    the frontend redirects to login.html after a successful signup.
    """
    try:
        data = request.get_json(silent=True) or {}

        full_name = str(data.get("full_name", "")).strip()
        email = str(data.get("email", "")).strip()
        password = str(data.get("password", ""))

        # ---- Input validation ----
        if not full_name or not email or not password:
            return jsonify({
                "success": False,
                "message": "full_name, email, and password are all required."
            }), 400

        if not is_valid_email(email):
            return jsonify({
                "success": False,
                "message": "Please provide a valid email address."
            }), 400

        if len(password) < 6:
            return jsonify({
                "success": False,
                "message": "Password must be at least 6 characters long."
            }), 400

        # ---- Prevent duplicate registration ----
        existing_user = db.get_user_by_email(email)
        if existing_user is not None:
            return jsonify({
                "success": False,
                "message": "An account with this email already exists."
            }), 409

        # ---- Hash password and store the new user ----
        password_hash = generate_password_hash(password)
        user_id = db.create_user(
            full_name=full_name,
            email=email,
            password_hash=password_hash
        )

        if user_id is None:
            # Covers the (rare) race condition where two signups for the
            # same email happen concurrently, as well as other DB errors.
            return jsonify({
                "success": False,
                "message": "Could not create account. The email may already be registered."
            }), 409

        logger.info("New user registered: '%s' (id=%s).", email, user_id)

        return jsonify({
            "success": True,
            "message": "Account created successfully"
        }), 201

    except Exception as error:
        logger.error("Error in /signup endpoint: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": "Signup failed due to a server error."
        }), 500


@app.route("/login", methods=["POST"])
def login():
    """
    Authenticate a user and issue a bearer token (Plan B -- no cookies).

    Expects JSON body:
        {
            "email": "john@example.com",
            "password": "password123"
        }

    Verifies the password against the stored hash with
    check_password_hash (inside db.verify_user) and, on success,
    generates a random token via db.create_token() and returns it in
    the JSON response body. The frontend is responsible for storing
    this token (e.g. in localStorage) and sending it back as
    "Authorization: Bearer <token>" on every protected request.
    """
    try:
        data = request.get_json(silent=True) or {}

        email = str(data.get("email", "")).strip()
        password = str(data.get("password", ""))

        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Email and password are required."
            }), 400

        user = db.verify_user(email, password)

        if user is None:
            # Deliberately vague: don't reveal whether the email exists.
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        # ---- Issue a bearer token for this login ----
        token = db.create_token(user["id"])

        if token is None:
            return jsonify({
                "success": False,
                "message": "Login succeeded but a session token could not be created. Please try again."
            }), 500

        logger.info("User '%s' (id=%s) logged in.", user["email"], user["id"])

        return jsonify({
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": public_user(user)
        }), 200

    except Exception as error:
        logger.error("Error in /login endpoint: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": "Login failed due to a server error."
        }), 500


@app.route("/logout", methods=["GET"])
def logout():
    """
    Log the user out by revoking their bearer token server-side.

    Reads the token from the Authorization header (if present) and
    deletes it from the Tokens table. Always returns success -- the
    frontend clears its local copy of the token regardless, so this
    route is idempotent whether or not a valid token was supplied.
    """
    try:
        token = get_bearer_token()
        if token:
            db.delete_token(token)

        return jsonify({
            "success": True
        }), 200

    except Exception as error:
        logger.error("Error in /logout endpoint: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": "Logout failed due to a server error."
        }), 500


@app.route("/me", methods=["GET"])
def current_user():
    """
    Return the currently logged-in user's public info, if any.

    Reads the token from the Authorization header. Useful for the
    frontend to check auth state (e.g. on every page load) without
    triggering a 401 -- this route is intentionally NOT behind
    @token_required, and always responds 200 with an
    "authenticated" flag instead.
    """
    token = get_bearer_token()

    if not token:
        return jsonify({
            "success": True,
            "authenticated": False,
            "user": None
        }), 200

    user = db.get_user_by_token(token)
    if user is None:
        # Token is missing, unknown, or was already revoked.
        return jsonify({
            "success": True,
            "authenticated": False,
            "user": None
        }), 200

    return jsonify({
        "success": True,
        "authenticated": True,
        "user": public_user(user)
    }), 200


# ---------------------------------------------------------------------------
# Routes - Resume Processing (Protected: bearer token required)
# ---------------------------------------------------------------------------
@app.route("/upload", methods=["POST"])
@token_required
def upload_resume():
    """
    Upload and end-to-end process a resume file:
    1. Validate and save file.
    2. Extract text using ResumeParser.
    3. Extract skills using SkillExtractor.
    4. Calculate ATS score using ATSScore.
    5. Recommend top matching jobs using JobRecommender.
    6. Store applicant details, skills, and recommendations in SQLite database.
    7. Return full structured JSON response.

    Requires a valid "Authorization: Bearer <token>" header (see
    token_required).
    """
    try:
        if "file" not in request.files:
            return jsonify({
                "success": False,
                "message": "No file part found in the request. Use the key 'file'."
            }), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({
                "success": False,
                "message": "No file selected. Please choose a resume to upload."
            }), 400

        if not allowed_file(file.filename):
            return jsonify({
                "success": False,
                "message": "Invalid file type. Only PDF and DOCX files are allowed."
            }), 400

        # Save uploaded file safely
        unique_filename = build_unique_filename(file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(save_path)
        logger.info("Saved uploaded file to: %s", save_path)

        # 1. Text Extraction
        resume_text = parser.extract_text(save_path)

        # 2. Skill Extraction
        skills_result = skill_extractor.extract_skills(resume_text)
        extracted_skills = skills_result.get("detected_skills", [])

        # Optional required skills parameter from form or request context
        required_skills_raw = request.form.get("required_skills", "")
        required_skills = [
            s.strip() for s in required_skills_raw.split(",") if s.strip()
        ] if required_skills_raw else []

        # 3. ATS Score Calculation
        ats_result = ats_scorer.calculate_score(
            resume_text=resume_text,
            extracted_skills=extracted_skills,
            required_skills=required_skills
        )

        overall_score = ats_result.get("overall_score", 0.0)
        grade = ats_result.get("grade", "D")
        feedback = {
            "strengths": ats_result.get("strengths", []),
            "weaknesses": ats_result.get("weaknesses", []),
            "suggestions": ats_result.get("suggestions", [])
        }

        # 4. Job Recommendations
        top_n = int(request.form.get("top_n", 10))
        recommended_jobs = recommender.recommend_jobs(extracted_skills, top_n=top_n)

        # 5. Extract Applicant Info & Save to Database
        applicant_info = extract_applicant_info(resume_text, unique_filename)

        applicant_id = db.add_applicant(
            full_name=applicant_info["full_name"],
            email=applicant_info["email"],
            phone=applicant_info["phone"],
            resume_filename=unique_filename,
            ats_score=overall_score
        )

        if applicant_id:
            db.add_skills(applicant_id, extracted_skills)
            db.add_recommendations(applicant_id, recommended_jobs)
            applicant_info["id"] = applicant_id

        logger.info("Successfully processed resume for '%s' (ID: %s)", applicant_info["full_name"], applicant_id)

        # 6. JSON Response Return
        return jsonify({
            "success": True,
            "message": "Resume uploaded and processed successfully.",
            "filename": unique_filename,
            "filepath": save_path,
            "applicant": applicant_info,
            "extracted_skills": extracted_skills,
            "skill_details": skills_result,
            "ats_score": overall_score,
            "grade": grade,
            "feedback": feedback,
            "ats_breakdown": ats_result.get("breakdown", {}),
            "recommended_jobs": recommended_jobs
        }), 201

    except Exception as error:
        logger.error("Error processing resume upload: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Upload and processing failed: {str(error)}"
        }), 500


@app.route("/analyze", methods=["POST"])
@token_required
def analyze_resume():
    """Parse resume text and extract structured skills data. Requires a bearer token."""
    try:
        data = request.get_json(silent=True) or {}
        filename = data.get("filename")

        if not filename:
            return jsonify({
                "success": False,
                "message": "Please provide a 'filename' in the JSON body."
            }), 400

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename))

        if not os.path.exists(file_path):
            return jsonify({
                "success": False,
                "message": "Resume file not found. Upload the file first."
            }), 404

        resume_text = parser.extract_text(file_path)
        skills_result = skill_extractor.extract_skills(resume_text)
        applicant_info = extract_applicant_info(resume_text, filename)

        return jsonify({
            "success": True,
            "message": "Resume analyzed successfully.",
            "filename": filename,
            "applicant": applicant_info,
            "data": {
                "extracted_skills": skills_result.get("detected_skills", []),
                "categories": skills_result.get("categories", {}),
                "skill_frequency": skills_result.get("skill_frequency", {}),
                "total_skills_found": skills_result.get("total_skills_found", 0)
            }
        }), 200

    except Exception as error:
        logger.error("Error in /analyze endpoint: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Analysis failed: {str(error)}"
        }), 500


@app.route("/score", methods=["POST"])
@token_required
def score_resume():
    """Calculate ATS score and return detailed feedback breakdown. Requires a bearer token."""
    try:
        data = request.get_json(silent=True) or {}
        filename = data.get("filename")
        required_skills = data.get("required_skills", [])

        if not filename:
            return jsonify({
                "success": False,
                "message": "Please provide a 'filename' in the JSON body."
            }), 400

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(filename))

        if not os.path.exists(file_path):
            return jsonify({
                "success": False,
                "message": "Resume file not found. Upload the file first."
            }), 404

        resume_text = parser.extract_text(file_path)
        skills_result = skill_extractor.extract_skills(resume_text)
        extracted_skills = skills_result.get("detected_skills", [])

        ats_result = ats_scorer.calculate_score(
            resume_text=resume_text,
            extracted_skills=extracted_skills,
            required_skills=required_skills
        )

        return jsonify({
            "success": True,
            "message": "ATS score computed successfully.",
            "filename": filename,
            "score": {
                "overall": ats_result.get("overall_score", 0.0),
                "grade": ats_result.get("grade", "D"),
                "breakdown": ats_result.get("breakdown", {}),
                "length_category": ats_result.get("length_category", "Unknown"),
                "word_count": ats_result.get("word_count", 0),
                "detected_sections": ats_result.get("detected_sections", []),
                "missing_sections": ats_result.get("missing_sections", []),
                "missing_skills": ats_result.get("missing_skills", []),
                "feedback": {
                    "strengths": ats_result.get("strengths", []),
                    "weaknesses": ats_result.get("weaknesses", []),
                    "suggestions": ats_result.get("suggestions", [])
                }
            }
        }), 200

    except Exception as error:
        logger.error("Error in /score endpoint: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Scoring failed: {str(error)}"
        }), 500


@app.route("/jobs", methods=["POST"])
@token_required
def get_job_recommendations():
    """Recommend jobs based on candidate skills. Requires a bearer token."""
    try:
        data = request.get_json(silent=True) or {}
        skills = data.get("skills", [])
        top_n = data.get("top_n", 10)

        if not skills:
            return jsonify({
                "success": False,
                "message": "Please provide a 'skills' list in the JSON body."
            }), 400

        recommendations = recommender.recommend_jobs(skills, top_n=top_n)

        return jsonify({
            "success": True,
            "message": "Job recommendations generated successfully.",
            "skills": skills,
            "recommendations": recommendations
        }), 200

    except Exception as error:
        logger.error("Error in /jobs endpoint: %s", str(error), exc_info=True)
        return jsonify({
            "success": False,
            "message": f"Job recommendation failed: {str(error)}"
        }), 500


# ---------------------------------------------------------------------------
# Run Development Server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Bound to 127.0.0.1 to match auth.js's apiBase ('http://127.0.0.1:5000')
    # and script.js's upload URL exactly -- keep these in sync if you ever
    # change one of them.
    app.run(host="127.0.0.1", port=5000, debug=True)