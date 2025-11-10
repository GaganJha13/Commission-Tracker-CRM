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
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-please-change-this")
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60  # token lifetime

DB_PATH = "solar_crm.db"   # your sqlite file

# Setup simple logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/queries.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

# ------------------------
#  Helpers
# ------------------------
def get_db_connection():
    """Return a sqlite3 connection with row access by name."""
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def generate_jwt(payload: dict) -> str:
    """Create JWT with expiry (centralized function)."""
    expiry = datetime.utcnow() + timedelta(minutes=JWT_EXP_MINUTES)
    payload_to_encode = payload.copy()
    payload_to_encode.update({"exp": expiry})
    token = jwt.encode(payload_to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    # PyJWT >=2 returns str, older versions return bytes
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token

def verify_jwt(token: str):
    """Verify and return payload or None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
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


@app.route("/logout", methods=["POST", "GET"])
def logout():
    """Clear cookie and revoke access token (by jti)."""
    token = request.cookies.get("access_token")
    # clear cookie in response
    resp = make_response(redirect(url_for("login")))
    resp.set_cookie("access_token", "", expires=0, httponly=True, samesite="Lax", secure=False)

    if token:
        # attempt to decode token without verification of expiry to extract jti safely
        try:
            # verify signature but ignore expiration? we'll try normal decode first
            payload = verify_jwt(token)
            if payload and payload.get("jti"):
                jti = payload["jti"]
            else:
                # try decode without expiration to get jti if expired (optional)
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
                jti = payload.get("jti")
        except Exception:
            jti = None

        if jti:
            try:
                conn = get_db_connection()
                conn.execute("INSERT OR IGNORE INTO revoked_tokens (jti) VALUES (?)", (jti,))
                conn.commit()
            finally:
                conn.close()

    return resp

# ------------------------
#  Run app
# ------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
