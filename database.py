"""
AI Resume Screening & Job Recommendation System
database.py
-------------------------------------------------------------
This module handles all SQLite database operations for the
backend: user authentication (Plan B: simple bearer tokens,
NOT Flask sessions/cookies), storing applicants, their
extracted skills, and their job recommendations.

Why tokens instead of Flask sessions?
--------------------------------------
Flask's built-in session relies on a signed cookie. That approach
turned out to be fragile in this project's dev setup (secret-key
rotation on every debug-reloader restart, SameSite/host mismatches
between the static frontend and the Flask backend, etc.) and was
the root cause of the resume upload endpoint returning 401
Unauthorized even right after a successful login.

Plan B removes cookies entirely:
    1. On login, the server generates a random opaque token and
       stores it in the new "Tokens" table, linked to the user.
    2. The token is returned in the JSON response body (not a
       cookie) and the frontend stores it in localStorage.
    3. Every subsequent protected request sends the token back
       manually via the "Authorization: Bearer <token>" header.
    4. The server looks the token up directly in this table --
       no signing, no cookies, no SameSite/CORS credential rules
       to get wrong.

This is intentionally simple (appropriate for a college project)
rather than a full JWT implementation, but it is not vulnerable to
any of the session/cookie issues described above.

This module is designed to be imported directly into app.py:

    from database import Database

    db = Database()

    # --- Authentication (Plan B: tokens) ---
    user_id = db.create_user(
        full_name="John Doe",
        email="john@example.com",
        password_hash="<werkzeug-hashed-password>"
    )
    user = db.verify_user("john@example.com", "password123")
    token = db.create_token(user["id"])
    user = db.get_user_by_token(token)
    db.delete_token(token)  # logout

    # --- Resume / Applicant workflow (unchanged) ---
    applicant_id = db.add_applicant(
        full_name="John Doe",
        email="john@example.com",
        phone="+1-555-123-4567",
        resume_filename="20260804_120000_resume.pdf",
        ats_score=82.5
    )
    db.add_skills(applicant_id, ["Python", "Flask", "SQL"])
    db.close_connection()

Tables created automatically inside resume.db:
    - Users           (registered accounts for authentication)
    - Tokens          (active bearer tokens, one row per login)
    - Applicants      (candidate profile + overall ATS score)
    - Skills          (skills linked to an applicant)
    - Recommendations (job recommendations linked to an applicant)
"""

import logging
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
# Matches the logging style used across resume_parser.py, skill_extractor.py,
# ats_score.py, and job_recommender.py so log output looks consistent
# across the whole backend.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Bearer tokens are 32 random bytes, hex-encoded -> 64 characters.
# This is cryptographically strong (secrets.token_hex uses os.urandom)
# and is *not* signed/stateless like a JWT -- it is only ever compared
# against the Tokens table, so revoking one is a single DELETE.
TOKEN_BYTES = 32


class Database:
    """
    Manages the SQLite database (resume.db) for the AI Resume Screening &
    Job Recommendation System: user accounts, bearer tokens, applicants,
    their extracted skills, and their job recommendations.
    """

    def __init__(self, db_name: str = "resume.db") -> None:
        """
        Initialize the Database class.

        On creation, this automatically:
            1. Connects to (or creates) the SQLite database file.
            2. Creates all required tables if they do not already exist.

        Args:
            db_name: Name/path of the SQLite database file.
                     Defaults to "resume.db" in the current working directory.
        """
        self.db_name: str = db_name
        self.connection: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

        # Automatically connect and set up tables on initialization,
        # following the same "ready to use immediately" pattern used
        # by JobRecommender in job_recommender.py.
        self.connect()
        self.create_tables()

    # -------------------------------------------------------------------
    # 1. CONNECTION HANDLING
    # -------------------------------------------------------------------
    def connect(self) -> Optional[sqlite3.Connection]:
        """
        Open a connection to the SQLite database file (resume.db).

        Also enables foreign key enforcement (OFF by default in SQLite)
        so that deleting a user/applicant can cascade to their related
        tokens/skills/recommendations, and sets row_factory so query
        results can be easily converted into dictionaries.

        Returns:
            The active sqlite3.Connection object, or None if the
            connection could not be established.
        """
        try:
            # check_same_thread=False allows this connection to be reused
            # safely across Flask's request-handling (single dev-server
            # process) without SQLite raising thread-safety errors.
            self.connection = sqlite3.connect(self.db_name, check_same_thread=False)

            # Return query results as sqlite3.Row objects, which behave
            # like dictionaries (access by column name) — much easier
            # to convert to JSON later in app.py.
            self.connection.row_factory = sqlite3.Row

            # Turn on foreign key constraint enforcement for this connection.
            self.connection.execute("PRAGMA foreign_keys = ON;")

            self.cursor = self.connection.cursor()
            logger.info("Connected to SQLite database: %s", self.db_name)
            return self.connection

        except sqlite3.Error as error:
            logger.error("Failed to connect to database '%s': %s", self.db_name, error)
            self.connection = None
            self.cursor = None
            return None

    # -------------------------------------------------------------------
    # 2. TABLE CREATION
    # -------------------------------------------------------------------
    def create_tables(self) -> bool:
        """
        Create the Users, Tokens, Applicants, Skills, and Recommendations
        tables if they do not already exist.

        Returns:
            bool: True if tables were created/verified successfully,
                  False if an error occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot create tables: no active database connection.")
                return False

            # ---- Users table (authentication) ----
            # "email" is UNIQUE so duplicate signups are rejected at the
            # database level as well as at the application level.
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS Users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            # ---- Tokens table (Plan B: simple bearer-token auth) ----
            # One row per active login. "token" is the primary key so
            # lookups on every protected request are a single indexed
            # equality check. Deleting the row = instant logout/revoke.
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS Tokens (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id)
                        REFERENCES Users (id)
                        ON DELETE CASCADE
                );
            """)

            # ---- Applicants table ----
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS Applicants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    upload_date TEXT NOT NULL,
                    resume_filename TEXT NOT NULL,
                    ats_score REAL DEFAULT 0
                );
            """)

            # ---- Skills table (many skills per applicant) ----
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS Skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_id INTEGER NOT NULL,
                    skill_name TEXT NOT NULL,
                    FOREIGN KEY (applicant_id)
                        REFERENCES Applicants (id)
                        ON DELETE CASCADE
                );
            """)

            # ---- Recommendations table (many jobs per applicant) ----
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS Recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    applicant_id INTEGER NOT NULL,
                    job_title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    match_percentage REAL DEFAULT 0,
                    salary TEXT,
                    apply_link TEXT,
                    FOREIGN KEY (applicant_id)
                        REFERENCES Applicants (id)
                        ON DELETE CASCADE
                );
            """)

            self.connection.commit()
            logger.info("Database tables verified/created successfully.")
            return True

        except sqlite3.Error as error:
            logger.error("Error creating tables: %s", error)
            return False

    # -------------------------------------------------------------------
    # 3. USER ACCOUNT OPERATIONS (signup / lookup / password check)
    # -------------------------------------------------------------------
    def create_user(self, full_name: str, email: str, password_hash: str) -> Optional[int]:
        """
        Insert a new user record into the Users table.

        The caller (app.py) is responsible for hashing the plain-text
        password with werkzeug's ``generate_password_hash`` before
        calling this method — this module never stores or receives
        plain-text passwords.

        Args:
            full_name: The new user's full name.
            email: The new user's email address (must be unique).
            password_hash: The already-hashed password string.

        Returns:
            The new user's id (int) if the insert succeeded, ``None``
            if the email is already registered or another database
            error occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot create user: no active database connection.")
                return None

            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Parameterized query prevents SQL injection.
            self.cursor.execute(
                """
                INSERT INTO Users (full_name, email, password, created_at)
                VALUES (?, ?, ?, ?);
                """,
                (full_name, email.strip().lower(), password_hash, created_at),
            )
            self.connection.commit()

            user_id = self.cursor.lastrowid
            logger.info("User created successfully with id=%s.", user_id)
            return user_id

        except sqlite3.IntegrityError:
            # Raised when the UNIQUE constraint on "email" is violated.
            logger.warning("Signup rejected: email '%s' is already registered.", email)
            return None

        except sqlite3.Error as error:
            logger.error("Error creating user: %s", error)
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single user record by email address.

        Args:
            email: The email address to look up (case-insensitive).

        Returns:
            A dictionary containing the user's stored fields (id,
            full_name, email, password [hashed], created_at), or
            ``None`` if no matching user was found or an error
            occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot get user: no active database connection.")
                return None

            self.cursor.execute(
                "SELECT * FROM Users WHERE email = ?;", (email.strip().lower(),)
            )
            user_row = self.cursor.fetchone()

            if user_row is None:
                return None

            return dict(user_row)

        except sqlite3.Error as error:
            logger.error("Error retrieving user by email '%s': %s", email, error)
            return None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single user record by id.

        Args:
            user_id: The id of the user to retrieve.

        Returns:
            A dictionary of the user's stored fields, or ``None`` if
            not found or an error occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot get user: no active database connection.")
                return None

            self.cursor.execute("SELECT * FROM Users WHERE id = ?;", (user_id,))
            user_row = self.cursor.fetchone()

            if user_row is None:
                return None

            return dict(user_row)

        except sqlite3.Error as error:
            logger.error("Error retrieving user by id=%s: %s", user_id, error)
            return None

    def verify_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Verify a user's login credentials.

        Looks up the user by email and checks the supplied plain-text
        password against the stored hash using werkzeug's
        ``check_password_hash``.

        Args:
            email: The email address supplied at login.
            password: The plain-text password supplied at login.

        Returns:
            The user's dictionary (including the hashed password) if
            the credentials are valid, otherwise ``None``.
        """
        try:
            user = self.get_user_by_email(email)
            if user is None:
                return None

            if not check_password_hash(user["password"], password):
                return None

            return user

        except (sqlite3.Error, ValueError) as error:
            # ValueError can be raised by check_password_hash on a
            # malformed hash — treat it the same as a failed login
            # rather than letting it crash the request.
            logger.error("Error verifying user '%s': %s", email, error)
            return None

    # -------------------------------------------------------------------
    # 4. TOKEN OPERATIONS (Plan B auth — replaces Flask sessions)
    # -------------------------------------------------------------------
    def create_token(self, user_id: int) -> Optional[str]:
        """
        Generate a new random bearer token for a user and store it.

        Called once, right after a successful /login. The returned
        token is what the frontend stores in localStorage and sends
        back on every protected request as:

            Authorization: Bearer <token>

        Args:
            user_id: The id of the user this token authenticates.

        Returns:
            The newly generated token string, or ``None`` if the
            insert failed.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot create token: no active database connection.")
                return None

            token = secrets.token_hex(TOKEN_BYTES)
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute(
                "INSERT INTO Tokens (token, user_id, created_at) VALUES (?, ?, ?);",
                (token, user_id, created_at),
            )
            self.connection.commit()

            logger.info("Issued new auth token for user_id=%s.", user_id)
            return token

        except sqlite3.Error as error:
            logger.error("Error creating token for user_id=%s: %s", user_id, error)
            return None

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a bearer token to the user it belongs to.

        This is the core of every protected-route check: the caller
        (app.py's token_required decorator) passes in whatever the
        client sent in its "Authorization: Bearer <token>" header.

        Args:
            token: The bearer token string to look up.

        Returns:
            The user's dictionary if the token exists and is linked
            to a real user, otherwise ``None`` (missing/unknown/
            revoked token — the caller should treat this as
            "not authenticated").
        """
        try:
            if not token:
                return None

            if self.connection is None or self.cursor is None:
                logger.error("Cannot resolve token: no active database connection.")
                return None

            self.cursor.execute(
                """
                SELECT Users.*
                FROM Tokens
                JOIN Users ON Users.id = Tokens.user_id
                WHERE Tokens.token = ?;
                """,
                (token,),
            )
            user_row = self.cursor.fetchone()

            if user_row is None:
                return None

            return dict(user_row)

        except sqlite3.Error as error:
            logger.error("Error resolving token: %s", error)
            return None

    def delete_token(self, token: str) -> bool:
        """
        Delete a bearer token (log the user out server-side).

        Safe to call with an unknown or already-deleted token — this
        simply results in zero rows affected, which is treated as a
        harmless no-op so /logout is always idempotent.

        Args:
            token: The bearer token string to revoke.

        Returns:
            bool: True if the token was found and deleted, False if
                  it did not exist or an error occurred.
        """
        try:
            if not token:
                return False

            if self.connection is None or self.cursor is None:
                logger.error("Cannot delete token: no active database connection.")
                return False

            self.cursor.execute("DELETE FROM Tokens WHERE token = ?;", (token,))
            self.connection.commit()

            deleted = self.cursor.rowcount > 0
            if deleted:
                logger.info("Auth token revoked.")
            return deleted

        except sqlite3.Error as error:
            logger.error("Error deleting token: %s", error)
            return False

    # -------------------------------------------------------------------
    # 5. APPLICANT OPERATIONS
    # -------------------------------------------------------------------
    def add_applicant(
        self,
        full_name: str,
        email: str,
        phone: str,
        resume_filename: str,
        ats_score: float = 0.0,
    ) -> Optional[int]:
        """
        Insert a new applicant record into the Applicants table.

        Args:
            full_name: Candidate's full name.
            email: Candidate's email address.
            phone: Candidate's phone number.
            resume_filename: Filename of the uploaded resume (as saved
                              on disk by app.py's /upload route).
            ats_score: Overall ATS score for this applicant (default 0.0).

        Returns:
            The new applicant's id (int) if the insert succeeded,
            or None if an error occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot add applicant: no active database connection.")
                return None

            upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Parameterized query (using "?" placeholders) prevents SQL
            # injection — user-supplied values are never string-formatted
            # directly into the SQL statement.
            self.cursor.execute(
                """
                INSERT INTO Applicants
                    (full_name, email, phone, upload_date, resume_filename, ats_score)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (full_name, email, phone, upload_date, resume_filename, ats_score),
            )
            self.connection.commit()

            applicant_id = self.cursor.lastrowid
            logger.info("Applicant added successfully with id=%s.", applicant_id)
            return applicant_id

        except sqlite3.Error as error:
            logger.error("Error adding applicant: %s", error)
            return None

    def get_applicant(self, applicant_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single applicant's full profile, including their
        associated skills and job recommendations.

        Args:
            applicant_id: The id of the applicant to retrieve.

        Returns:
            A dictionary containing the applicant's details, a
            "skills" list, and a "recommendations" list — or None
            if the applicant was not found or an error occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot get applicant: no active database connection.")
                return None

            self.cursor.execute(
                "SELECT * FROM Applicants WHERE id = ?;", (applicant_id,)
            )
            applicant_row = self.cursor.fetchone()

            if applicant_row is None:
                logger.warning("No applicant found with id=%s.", applicant_id)
                return None

            applicant_data = dict(applicant_row)

            # Attach related skills.
            self.cursor.execute(
                "SELECT skill_name FROM Skills WHERE applicant_id = ?;",
                (applicant_id,),
            )
            applicant_data["skills"] = [row["skill_name"] for row in self.cursor.fetchall()]

            # Attach related job recommendations.
            self.cursor.execute(
                "SELECT job_title, company, location, match_percentage, "
                "salary, apply_link FROM Recommendations WHERE applicant_id = ?;",
                (applicant_id,),
            )
            applicant_data["recommendations"] = [
                dict(row) for row in self.cursor.fetchall()
            ]

            return applicant_data

        except sqlite3.Error as error:
            logger.error("Error retrieving applicant id=%s: %s", applicant_id, error)
            return None

    def get_all_applicants(self) -> List[Dict[str, Any]]:
        """
        Retrieve a summary list of all applicants stored in the database
        (without their nested skills/recommendations, for performance).

        Returns:
            A list of applicant dictionaries, ordered by most recently
            uploaded first. Returns an empty list if none exist or an
            error occurs.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot get applicants: no active database connection.")
                return []

            self.cursor.execute(
                "SELECT * FROM Applicants ORDER BY upload_date DESC;"
            )
            rows = self.cursor.fetchall()

            applicants = [dict(row) for row in rows]
            logger.info("Retrieved %d applicant(s) from the database.", len(applicants))
            return applicants

        except sqlite3.Error as error:
            logger.error("Error retrieving all applicants: %s", error)
            return []

    def update_ats_score(self, applicant_id: int, new_score: float) -> bool:
        """
        Update the ATS score for an existing applicant.

        Args:
            applicant_id: The id of the applicant to update.
            new_score: The new ATS score to store.

        Returns:
            bool: True if the update affected a row, False otherwise
                  (e.g. applicant not found, or an error occurred).
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot update ATS score: no active database connection.")
                return False

            self.cursor.execute(
                "UPDATE Applicants SET ats_score = ? WHERE id = ?;",
                (new_score, applicant_id),
            )
            self.connection.commit()

            if self.cursor.rowcount == 0:
                logger.warning(
                    "update_ats_score(): no applicant found with id=%s.", applicant_id
                )
                return False

            logger.info(
                "ATS score updated to %s for applicant id=%s.", new_score, applicant_id
            )
            return True

        except sqlite3.Error as error:
            logger.error("Error updating ATS score for id=%s: %s", applicant_id, error)
            return False

    def delete_applicant(self, applicant_id: int) -> bool:
        """
        Delete an applicant and all of their related skills and job
        recommendations (cascading delete).

        Args:
            applicant_id: The id of the applicant to delete.

        Returns:
            bool: True if the applicant was deleted, False if the
                  applicant was not found or an error occurred.
        """
        try:
            if self.connection is None or self.cursor is None:
                logger.error("Cannot delete applicant: no active database connection.")
                return False

            # Explicitly delete related rows first as a safety net, in
            # addition to the "ON DELETE CASCADE" foreign keys — this
            # guarantees clean-up even if PRAGMA foreign_keys was ever
            # disabled for a given connection.
            self.cursor.execute(
                "DELETE FROM Skills WHERE applicant_id = ?;", (applicant_id,)
            )
            self.cursor.execute(
                "DELETE FROM Recommendations WHERE applicant_id = ?;", (applicant_id,)
            )
            self.cursor.execute(
                "DELETE FROM Applicants WHERE id = ?;", (applicant_id,)
            )
            self.connection.commit()

            if self.cursor.rowcount == 0:
                logger.warning(
                    "delete_applicant(): no applicant found with id=%s.", applicant_id
                )
                return False

            logger.info("Applicant id=%s deleted successfully.", applicant_id)
            return True

        except sqlite3.Error as error:
            logger.error("Error deleting applicant id=%s: %s", applicant_id, error)
            return False

    # -------------------------------------------------------------------
    # 6. SKILLS OPERATIONS
    # -------------------------------------------------------------------
    def add_skills(self, applicant_id: int, skills: List[str]) -> bool:
        """
        Save a list of extracted skills for a given applicant.

        Args:
            applicant_id: The id of the applicant these skills belong to.
            skills: List of skill names (e.g. from skill_extractor.py's
                    extract_skills() -> "detected_skills").

        Returns:
            bool: True if the skills were saved successfully (or the
                  list was empty), False if an error occurred.
        """
        try:
            if not skills:
                logger.info("add_skills(): no skills provided for applicant id=%s.", applicant_id)
                return True

            if self.connection is None or self.cursor is None:
                logger.error("Cannot add skills: no active database connection.")
                return False

            # executemany() efficiently inserts multiple rows using the
            # same parameterized query.
            skill_rows = [(applicant_id, skill) for skill in skills]
            self.cursor.executemany(
                "INSERT INTO Skills (applicant_id, skill_name) VALUES (?, ?);",
                skill_rows,
            )
            self.connection.commit()

            logger.info(
                "Saved %d skill(s) for applicant id=%s.", len(skills), applicant_id
            )
            return True

        except sqlite3.Error as error:
            logger.error("Error adding skills for applicant id=%s: %s", applicant_id, error)
            return False

    # -------------------------------------------------------------------
    # 7. RECOMMENDATIONS OPERATIONS
    # -------------------------------------------------------------------
    def add_recommendations(
        self, applicant_id: int, recommendations: List[Dict[str, Any]]
    ) -> bool:
        """
        Save a list of job recommendations for a given applicant.

        Args:
            applicant_id: The id of the applicant these recommendations
                          belong to.
            recommendations: List of job recommendation dictionaries
                              (e.g. from job_recommender.py's
                              recommend_jobs()). Each dict is expected
                              to contain: job_title, company, location,
                              match_percentage, salary, apply_link.
                              Missing keys default to safe empty values.

        Returns:
            bool: True if the recommendations were saved successfully
                  (or the list was empty), False if an error occurred.
        """
        try:
            if not recommendations:
                logger.info(
                    "add_recommendations(): no recommendations provided for applicant id=%s.",
                    applicant_id,
                )
                return True

            if self.connection is None or self.cursor is None:
                logger.error("Cannot add recommendations: no active database connection.")
                return False

            recommendation_rows = [
                (
                    applicant_id,
                    job.get("job_title", "N/A"),
                    job.get("company", "N/A"),
                    job.get("location", "N/A"),
                    job.get("match_percentage", 0.0),
                    job.get("salary", "N/A"),
                    job.get("apply_link", "#"),
                )
                for job in recommendations
            ]

            self.cursor.executemany(
                """
                INSERT INTO Recommendations
                    (applicant_id, job_title, company, location,
                     match_percentage, salary, apply_link)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                recommendation_rows,
            )
            self.connection.commit()

            logger.info(
                "Saved %d recommendation(s) for applicant id=%s.",
                len(recommendations),
                applicant_id,
            )
            return True

        except sqlite3.Error as error:
            logger.error(
                "Error adding recommendations for applicant id=%s: %s", applicant_id, error
            )
            return False

    # -------------------------------------------------------------------
    # 8. CONNECTION CLEANUP
    # -------------------------------------------------------------------
    def close_connection(self) -> None:
        """
        Commit any pending changes and close the database connection
        and cursor. Safe to call even if the connection was never
        opened successfully.
        """
        try:
            if self.connection is not None:
                self.connection.commit()
                self.connection.close()
                logger.info("Database connection to '%s' closed.", self.db_name)
            self.connection = None
            self.cursor = None

        except sqlite3.Error as error:
            logger.error("Error closing database connection: %s", error)


# ---------------------------------------------------------------------------
# STANDALONE DEMO / TEST BLOCK
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # This block only runs when the file is executed directly
    # (e.g. `python database.py`), NOT when it is imported into app.py.
    # It demonstrates the full workflow: creating the database and
    # tables, registering a user, logging in via a token, adding a
    # sample applicant, skills, and recommendations, retrieving the
    # stored data, and closing the connection.

    from werkzeug.security import generate_password_hash

    print("=" * 60)
    print("DATABASE MODULE - DEMO")
    print("=" * 60)

    # 1. Create the database (this also creates the tables automatically).
    db = Database(db_name="resume.db")

    # 2. Register a demo user account.
    demo_user_id = db.create_user(
        full_name="Demo User",
        email="demo.user@example.com",
        password_hash=generate_password_hash("SuperSecret123"),
    )
    print(f"\nDemo user created with id: {demo_user_id}")

    # 3. Log in: verify credentials, then issue a bearer token.
    verified = db.verify_user("demo.user@example.com", "SuperSecret123")
    print("Login check (correct password):", verified is not None)

    demo_token = db.create_token(demo_user_id) if verified else None
    print(f"Issued token: {demo_token}")

    # 4. Resolve the token back to a user, exactly like token_required
    #    does on every protected route in app.py.
    resolved_user = db.get_user_by_token(demo_token) if demo_token else None
    print("Token resolves to user:", resolved_user["email"] if resolved_user else None)

    # 5. Add a sample applicant.
    new_applicant_id = db.add_applicant(
        full_name="Jane Smith",
        email="jane.smith@example.com",
        phone="+1-555-987-6543",
        resume_filename="20260804_120000_jane_resume.pdf",
        ats_score=87.5,
    )
    print(f"\nNew applicant created with id: {new_applicant_id}")

    if new_applicant_id is not None:
        # 6. Save sample skills for this applicant.
        sample_skills = ["Python", "Flask", "SQL", "Machine Learning", "Git"]
        db.add_skills(new_applicant_id, sample_skills)
        print(f"Saved skills: {sample_skills}")

        # 7. Save sample job recommendations for this applicant.
        sample_recommendations = [
            {
                "job_title": "Backend Developer",
                "company": "Tech Corp",
                "location": "Remote",
                "match_percentage": 92.0,
                "salary": "$90,000 - $110,000",
                "apply_link": "https://example.com/apply/1",
            },
            {
                "job_title": "Machine Learning Engineer",
                "company": "AI Innovations",
                "location": "San Francisco, CA",
                "match_percentage": 78.5,
                "salary": "$130,000 - $160,000",
                "apply_link": "https://example.com/apply/2",
            },
        ]
        db.add_recommendations(new_applicant_id, sample_recommendations)
        print(f"Saved {len(sample_recommendations)} job recommendation(s).")

        # 8. Retrieve and display the full applicant profile.
        applicant_profile = db.get_applicant(new_applicant_id)
        print("\n--- Retrieved Applicant Profile ---")
        print(applicant_profile)

        # 9. Update the applicant's ATS score.
        db.update_ats_score(new_applicant_id, 90.0)
        print(f"\nATS score updated. New profile:")
        print(db.get_applicant(new_applicant_id))

    # 10. Log out: revoke the token and confirm it no longer resolves.
    if demo_token:
        db.delete_token(demo_token)
        print("\nToken revoked. Resolves after logout:",
              db.get_user_by_token(demo_token))

    # 11. Retrieve all applicants currently stored in the database.
    all_applicants = db.get_all_applicants()
    print(f"\n--- All Applicants ({len(all_applicants)}) ---")
    for applicant in all_applicants:
        print(applicant)

    # 12. Close the database connection.
    db.close_connection()
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)