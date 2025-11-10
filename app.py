# app.py (or import from auth_routes.py)
import sqlite3
from flask import Flask, request, render_template, redirect, url_for, make_response, jsonify
import bcrypt
import jwt
from functools import wraps
from datetime import datetime, timedelta
import logging
import os
from bot import process_message as bot_process_message


# ------------------------
#  Config
# ------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
# In production, read secret from env var and keep it private
JWT_SECRET = "a8c29b77b9f5416db0aef47efb7f24d1b5c6ab8d3a9c97b44151c0df412a54b0"
JWT_ALGORITHM = "HS256"


DB_PATH = "solar_crm.db"   # your sqlite file

# Setup simple logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/queries.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

# Ensure database exists at startup
try:
    from crm_database import create_database
except Exception:
    create_database = None

def ensure_db():
    if not os.path.exists(DB_PATH):
        logging.info("Database file %s not found; creating...", DB_PATH)
        if create_database:
            try:
                create_database(DB_PATH)
                logging.info("Database created successfully.")
            except Exception as e:
                logging.exception("Failed to create DB via crm_database.create_database(): %s", e)
                raise
        else:
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.close()
                logging.info("Created empty sqlite file %s (no schema).", DB_PATH)
            except Exception as e:
                logging.exception("Failed to create empty DB file %s: %s", DB_PATH, e)
                raise

# Run this check at startup
ensure_db()
# ------------------------
#  Helpers
# ------------------------
def get_db_connection():
    """Return a sqlite3 connection with row access by name."""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def generate_jwt(payload: dict) -> str:
    """
    Create a JWT WITHOUT an 'exp' claim. Token will remain valid
    until the cookie is cleared on logout (or secret is rotated).
    """
    payload_to_encode = payload.copy()
    token = jwt.encode(payload_to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def verify_jwt(token: str):
    """Verify JWT signature and return payload or None if invalid."""
    try:
        # decode and verify signature; do NOT check expiry (we didn't set one)
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        return payload
    except jwt.InvalidTokenError:
        return None



def login_required(view_func):
    """Decorator to protect routes that require a valid JWT cookie."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        token = request.cookies.get("access_token")
        if not token:
            return redirect(url_for("login"))
        payload = verify_jwt(token)
        if not payload:
            # token invalid or expired
            resp = make_response(redirect(url_for("login")))
            # clear cookie
            resp.set_cookie("access_token", "", expires=0, httponly=True, samesite="Lax")
            return resp
        # attach user info on request context for handlers
        request.user = payload
        return view_func(*args, **kwargs)
    return wrapped

# ------------------------
#  Routes
# ------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    """
    Secure login endpoint:
    - Renders login.html on GET
    - Handles form on POST
    - Displays Jinja error messages if invalid
    """
    # Show form on GET
    if request.method == "GET":
        return render_template("login.html")

    # --- POST: handle form submission ---
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Please enter both email and password.")

    conn = get_db_connection()
    try:
        cur = conn.execute(
            "SELECT agent_id, name, email, password_hash, role FROM user_employees WHERE lower(email)=lower(?)",
            (email,)
        )
        user = cur.fetchone()
    finally:
        conn.close()

    # Validate credentials
    if not user or not user["password_hash"]:
        return render_template("login.html", error="Invalid email or password.")

    # Normalize stored hash to bytes and verify with bcrypt
    try:
        stored_hash = user["password_hash"]
        if isinstance(stored_hash, str):
            stored_bytes = stored_hash.encode("utf-8")
        else:
            stored_bytes = stored_hash  # already bytes
        password_matches = bcrypt.checkpw(password.encode("utf-8"), stored_bytes)
    except Exception as e:
        # log the exact error to logs/queries.log for debugging (do not show to user)
        logging.exception("Error verifying password for %s: %s", email, e)
        return render_template("login.html", error="Internal server error. Try again later.")

    if not password_matches:
        return render_template("login.html", error="Invalid email or password.")

    # Successful login -> generate JWT and redirect to chat
    payload = {
        "agent_id": user["agent_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"]
    }
    token = generate_jwt(payload)

    resp = make_response(redirect(url_for("chat")))
    resp.set_cookie(
        "access_token",
        token,
        httponly=True,
        samesite="Strict",
        secure=False  # change to True when using HTTPS in production
    )
    logging.info("Login success for %s", email)
    return resp




@app.route("/chat", methods=["GET"])
@login_required
def chat():
    """
    Protected chat page — only accessible with valid JWT cookie.
    request.user is set by the decorator and contains user info.
    """
    user = getattr(request, "user", {})
    # optional: send user info to template if needed
    return render_template("chat.html", user_name=user.get("name"))


@app.route("/api/message", methods=["POST"])
@login_required
def api_message():
    """
    Protected API for chat messages.
    Expects JSON: { "text": "..." }
    Uses JWT cookie to identify user (login_required sets request.user)
    """
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "text": "Please send a non-empty message."}), 400

    user_payload = getattr(request, "user", None) or {}
    # process message via bot module
    result = bot_process_message(user_payload, text)
    status = 200 if result.get("ok", False) else 500
    return jsonify(result), status


@app.route("/logout", methods=["POST"])
def logout():
    """Clear cookie to log the user out (no server-side revocation)."""
    resp = make_response(redirect(url_for("login")))
    resp.set_cookie("access_token", "", expires=0, httponly=True, samesite="Lax", secure=False)
    return resp

# ------------------------
#  Run app
# ------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
