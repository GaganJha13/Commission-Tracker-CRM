# bot.py
"""
bot.py
Chat processing module for Solar CRM chatbot.

Public function:
    process_message(user_payload: dict, text: str) -> dict
        - user_payload is the JWT payload (agent_id, email, name, role)
        - text is raw user message
        returns: dict with keys: ok (bool), text (str)
"""

import re
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Tuple

# -- Database helper (lightweight) --
DB_PATH = "solar_crm.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    # enforce foreign keys for SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# -- Logging (uses the same logs directory as app) --
logger = logging.getLogger("bot")
if not logger.handlers:
    # configure logger if not already configured by app.py
    handler = logging.FileHandler("logs/queries.log")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# -- Simple intent detection patterns --
PAYMENT_KEYWORDS = re.compile(r'\b(payments?|payouts?|paid|received)\b', flags=re.I)
DATE_RANGE_PATTERN = re.compile(r'between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})', flags=re.I)
SINGLE_DATE_PATTERN = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')
THIS_MONTH = re.compile(r'\bthis month\b', flags=re.I)
LAST_MONTH = re.compile(r'\blast month\b', flags=re.I)
THIS_WEEK = re.compile(r'\bthis week\b', flags=re.I)
LAST_WEEK = re.compile(r'\blast week\b', flags=re.I)

ORDER_PATTERNS = [
    re.compile(r'project details for ([A-Za-z\s]+)', flags=re.I),
    re.compile(r'what is the system size for ([A-Za-z\s]+)', flags=re.I),
    re.compile(r'current stage for order of ([A-Za-z\s]+)', flags=re.I),
    re.compile(r'payment received for ([A-Za-z\s]+)', flags=re.I),
    re.compile(r'complete status for ([A-Za-z\s]+)', flags=re.I),
    re.compile(r'order of ([A-Za-z\s]+)', flags=re.I),
    re.compile(r'order for ([A-Za-z\s]+)', flags=re.I),
]

ALLOWED_STAGES = {
    "Project Acceptance", "Engineering", "Permitting", "Install Scheduled",
    "Installation Complete", "Inspection", "PTO", "Cancel", "Hold"
}

# -- Utilities for parsing dates --
def parse_date_range_from_text(text: str) -> Optional[Tuple[str, str]]:
    """
    Returns (start_iso, end_iso) or None.
    Recognises:
      - 'between YYYY-MM-DD and YYYY-MM-DD'
      - 'this month', 'last month', 'this week', 'last week'
      - single date YYYY-MM-DD (treated as that day)
    """
    today = datetime.utcnow().date()

    m = DATE_RANGE_PATTERN.search(text)
    if m:
        try:
            start = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            end = datetime.strptime(m.group(2), "%Y-%m-%d").date()
            return (start.isoformat(), end.isoformat())
        except ValueError:
            return None

    if THIS_MONTH.search(text):
        start = today.replace(day=1)
        # end of month:
        next_month = (start + timedelta(days=32)).replace(day=1)
        end = next_month - timedelta(days=1)
        return (start.isoformat(), end.isoformat())

    if LAST_MONTH.search(text):
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        start = last_month_end.replace(day=1)
        return (start.isoformat(), last_month_end.isoformat())

    if THIS_WEEK.search(text):
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)
        return (start.isoformat(), end.isoformat())

    if LAST_WEEK.search(text):
        start = today - timedelta(days=today.weekday()) - timedelta(days=7)
        end = start + timedelta(days=6)
        return (start.isoformat(), end.isoformat())

    m = SINGLE_DATE_PATTERN.search(text)
    if m:
        try:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            return (d.isoformat(), d.isoformat())
        except ValueError:
            return None

    return None

def extract_customer_name(text: str) -> Optional[str]:
    """
    Improved extractor for customer names.
    - Accepts explicit patterns like:
        "project details for Rahul Sharma"
        "what is the system size for customer Rahul Sharma"
        "complete status of Deepak"
    - Strips common leading tokens like 'customer', 'mr', 'ms', 'mrs'.
    Returns cleaned name or None.
    NOTE: intentionally does NOT include a broad fallback that matches any token,
    to avoid false positives for gibberish.
    """
    text = text.strip()

    # ordered patterns to match explicit queries only
    patterns = [
        r'(?:project details(?:\s+for)?|show project details(?:\s+for)?|project for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:what is the system size for|system size for|size is)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:current stage for order of|current stage for|current stage of|stage for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:payment received for|payments for|payment for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:complete status for|complete status of|complete status|show status for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:order of|order for|order)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'customer\s+([A-Za-z][A-Za-z\s]+)'
    ]

    for patt in patterns:
        m = re.search(patt, text, flags=re.I)
        if m:
            name = m.group(1).strip()
            # strip leading honorifics or noise words if present
            name = re.sub(r'^(customer|mr|mrs|ms|miss|dr)\s+', '', name, flags=re.I)
            name = re.sub(r'\s+', ' ', name).strip()
            # remove trailing noise words like 'please'
            name = re.sub(r'\b(please|now|today)\b', '', name, flags=re.I).strip()
            name = re.sub(r'^(for|of)\s+', '', name, flags=re.I)
            # ensure minimum reasonable length (at least 3 chars)
            if len(name) >= 3 and re.search(r'[A-Za-z]', name):
                return name
    return None
def is_gibberish_or_greeting(text: str) -> bool:
    """
    Very small heuristic:
      - common greetings like hello/hi/hey -> True
      - very short or non-letter heavy strings -> True (e.g. 'sadsada' will be treated as gibberish)
      - otherwise False
    This helps us return the friendly fallback message instead of 'No orders found...'
    """
    text = text.strip()
    if not text:
        return True

    # greetings
    if re.fullmatch(r'\b(hi|hello|hey|hola|yo|good morning|good evening)\b', text, flags=re.I):
        return True

    # if it contains many non-letter chars or is a single token of 1-2 chars
    only_letters = re.sub(r'[^A-Za-z]', '', text)
    if len(only_letters) < 3:
        return True

    # low "english-likeness": many repeated letters sequence (simple heuristic)
    if re.search(r'(.)\1\1\1', text):  # same char repeated 4 times
        return True

    return False

# -- DB access functions (safe parameterized queries) --
def fetch_payouts_for_agent(agent_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    Returns list of rows (sqlite3.Row) for payouts and total sum.
    """
    conn = get_db_connection()
    try:
        params = [agent_id]
        sql = "SELECT payout_id, order_id, amount, payment_type, submitted_date FROM payout_submitted WHERE agent_id = ?"
        if start_date and end_date:
            sql += " AND submitted_date BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        sql += " ORDER BY submitted_date DESC, payout_id DESC"
        logger.info("SQL: %s | params=%s", sql, params)
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            return [],0

        # compute total safely in Python to avoid any SQL sum differences
        total = sum([float(r["amount"]) for r in rows]) if rows else 0.0
        
        if not rows:
            return f"No payouts found for the period {start_date} to {end_date}."
        return rows, total
    finally:
        conn.close()

def find_orders_by_customer_name(name: str):
    """
    Case-insensitive exact and then LIKE search for orders matching customer name.
    Returns list of orders rows.
    """
    conn = get_db_connection()
    try:
        # try exact case-insensitive first
        sql1 = "SELECT order_id, customer_name, customer_email, system_size_kw, closer_id, deal_close_date FROM orders WHERE lower(customer_name) = lower(?)"
        logger.info("SQL: %s | params=%s", sql1, (name,))
        rows = conn.execute(sql1, (name,)).fetchall()
        if rows:
            return rows
        # partial match fallback
        sql2 = "SELECT order_id, customer_name, customer_email, system_size_kw, closer_id, deal_close_date FROM orders WHERE customer_name LIKE ?"
        likeparam = f"%{name}%"
        logger.info("SQL: %s | params=%s", sql2, (likeparam,))
        rows = conn.execute(sql2, (likeparam,)).fetchall()
        return rows
    finally:
        conn.close()

def handle_list_employees() -> str:
    """
    Return newline-separated list of employee names.
    Example:
      Alice Johnson
      Bob Singh
      Charlie Verma
    """
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT name FROM user_employees ORDER BY name ASC").fetchall()
        if not rows:
            return "No employees found."
        lines = [r["name"] for r in rows]
        # join with newlines for clean display; front-end should use pre-wrap.
        return "\n".join(lines)
    finally:
        conn.close()


def handle_list_customers() -> str:
    """
    Return newline-separated list of customers from orders table (unique & ordered).
    Example:
      Rahul Sharma
      Amit Singh
      ...
    """
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT customer_name FROM orders WHERE customer_name IS NOT NULL ORDER BY customer_name ASC"
        ).fetchall()
        if not rows:
            return "No customers found."
        lines = [r["customer_name"] for r in rows]
        return "\n".join(lines)
    finally:
        conn.close()

def fetch_latest_stage_for_order(order_id: int):
    conn = get_db_connection()
    try:
        sql = "SELECT stage, comment, updated_by, updated_at FROM orders_stage WHERE order_id = ? ORDER BY updated_at DESC, stage_id DESC LIMIT 1"
        logger.info("SQL: %s | params=%s", sql, (order_id,))
        row = conn.execute(sql, (order_id,)).fetchone()
        return row
    finally:
        conn.close()

def fetch_all_stages_for_order(order_id: int):
    conn = get_db_connection()
    try:
        sql = "SELECT stage, comment, updated_by, updated_at FROM orders_stage WHERE order_id = ? ORDER BY updated_at ASC, stage_id ASC"
        logger.info("SQL: %s | params=%s", sql, (order_id,))
        rows = conn.execute(sql, (order_id,)).fetchall()
        return rows
    finally:
        conn.close()

# -- Message handlers --
def handle_payment_query(agent_id: int, text: str) -> str:
    """
    Return a nicely formatted list of payouts for the agent in the requested date range.
    Output example:
      Total payout amount between 2025-01-10 and 2025-01-25: ₹30,000.00
        1) M1      - ₹30,000.00 - Order #1 - Rahul Sharma - 2025-01-15
        2) ADVANCE - ₹5,000.00  - (No Order) - - - 2025-06-01
    """
    dates = parse_date_range_from_text(text)
    if not dates:
        # default: last 30 days
        end = datetime.utcnow().date()
        start = end - timedelta(days=30)
        dates = (start.isoformat(), end.isoformat())

    start_date, end_date = dates
    rows, total = fetch_payouts_for_agent(agent_id, start_date, end_date)

    if not rows:
        return f"No payouts found for the period {start_date} to {end_date}."

    # Build structured output
    lines = []
    lines.append(f"Total payout amount between {start_date} and {end_date}: ₹{total:,.2f}")
    lines.append("")  # blank line

    # We will show newest first (rows already ordered by submitted_date DESC)
    for idx, r in enumerate(rows, start=1):
        payment_type = r["payment_type"] or "-"
        amount = float(r["amount"] or 0.0)
        submitted_date = r["submitted_date"] or "-"
        order_id = r["order_id"]
        order_ref = f"Order #{order_id}" if order_id else "(No Order)"
        customer = "-"
        if order_id:
            try:
                conn = get_db_connection()
                o = conn.execute("SELECT customer_name FROM orders WHERE order_id = ?", (order_id,)).fetchone()
                if o and o["customer_name"]:
                    customer = o["customer_name"]
            finally:
                conn.close()

        # Align fields a bit for readability (not strictly necessary)
        # type_field width 8, amount right-aligned
        type_field = f"{payment_type}"
        amount_field = f"₹{amount:,.2f}"
        lines.append(f"{idx}) {type_field:<8} - {amount_field:>11} - {order_ref} - {customer} - {submitted_date}")

    return "\n".join(lines)


def handle_customer_payment_query(agent_id: int, text: str) -> str:
    """
    Return structured payouts for a specific customer (by order).
    Example:
      Total payments received for Rahul Sharma: ₹75,000.00
        1) M1      - ₹30,000.00 - 2025-01-15
        2) M2      - ₹20,000.00 - 2025-02-10
        3) M1      - ₹25,000.00 - 2025-01-20
    """
    # extract and validate name
    customer_name = extract_customer_name(text)
    if not customer_name:
        return "Please specify a customer name."

    conn = get_db_connection()
    try:
        # prefer exact or closest match
        order_row = conn.execute(
            "SELECT order_id, customer_name FROM orders WHERE lower(customer_name) = lower(?) LIMIT 1",
            (customer_name,)
        ).fetchone()
        if not order_row:
            order_row = conn.execute("SELECT order_id, customer_name FROM orders WHERE customer_name LIKE ? LIMIT 1", (f"%{customer_name}%",)).fetchone()
            if not order_row:
                return f"No information found for customer matching '{customer_name}'."

        order_id = order_row["order_id"]
        canonical_name = order_row["customer_name"] or customer_name

        payouts = conn.execute(
            "SELECT payout_id, amount, payment_type, submitted_date FROM payout_submitted WHERE order_id = ? ORDER BY submitted_date DESC, payout_id DESC",
            (order_id,)
        ).fetchall()

        if not payouts:
            return f"No payouts found for customer {canonical_name}."

        total = sum([float(p["amount"]) for p in payouts])
        lines = []
        lines.append(f"Total payments received for {canonical_name}: ₹{total:,.2f}")
        lines.append("")  # blank

        for idx, p in enumerate(payouts, start=1):
            p_type = p["payment_type"] or "-"
            p_amount = float(p["amount"] or 0.0)
            p_date = p["submitted_date"] or "-"
            lines.append(f"{idx}) {p_type:<8} - ₹{p_amount:,.2f} - {p_date}")

        return "\n".join(lines)
    finally:
        conn.close()


def handle_order_query(text: str) -> str:
    """
    Smart order query handler that returns nicely structured multi-line blocks.
    Each order is rendered as:
      Order #<id>
      Customer   : <name>
      System Size: <x.x> kW
      Deal Date  : YYYY-MM-DD
      Current Stage: <stage> (updated: <timestamp>)
      Notes      : <comment>

    For intent-specific queries (system size, deal date, current stage) this returns
    only the relevant labeled lines for each matching order.
    """
    name = extract_customer_name(text)
    if not name:
        return "I couldn't identify the customer name in your message. Try: 'Show project details for customer Rahul Sharma'."

    orders = find_orders_by_customer_name(name)
    if not orders:
        return f"No information found for customer matching '{name}'."

    text_low = text.lower()
    wants_full = bool(re.search(r'\b(full|project details|complete status|show project details|complete status for)\b', text_low))
    wants_system_size = bool(re.search(r'\b(system size|what is the system size|size is)\b', text_low))
    wants_deal_date = bool(re.search(r'\b(deal date|when (?:was|did)|deal_date|deal date for)\b', text_low))
    wants_current_stage = bool(re.search(r'\b(current stage|stage for|what is the stage|order status|current status|status of order)\b', text_low))

    blocks = []

    # Helper to format a single order as a block
    def format_order_block(o, include_stage=True):
        lines = []
        lines.append(f"Order #{o['order_id']}")
        lines.append(f"Customer   : {o['customer_name']}")
        lines.append(f"System Size: {o['system_size_kw']} kW")
        lines.append(f"Deal Date  : {o['deal_close_date']}")
        if include_stage:
            latest = fetch_latest_stage_for_order(o['order_id'])
            if latest:
                lines.append(f"Current Stage: {latest['stage']} (updated: {latest['updated_at']})")
                lines.append(f"Notes        : {latest['comment'] or '-'}")
            else:
                lines.append("Current Stage: -")
                lines.append("Notes        : -")
        return "\n".join(lines)

    # If user explicitly asked for system size
    if wants_system_size and not (wants_full or wants_deal_date or wants_current_stage):
        for o in orders:
            blocks.append(f"Order #{o['order_id']} — System Size: {o['system_size_kw']} kW")
        return "\n\n".join(blocks)

    # If user asked for deal date
    if wants_deal_date and not (wants_full or wants_system_size or wants_current_stage):
        for o in orders:
            blocks.append(f"Order #{o['order_id']} — Deal Date: {o['deal_close_date']}")
        return "\n\n".join(blocks)

    # If user asked for current stage only
    if wants_current_stage and not (wants_full or wants_system_size or wants_deal_date):
        for o in orders:
            latest = fetch_latest_stage_for_order(o['order_id'])
            if latest:
                blocks.append(
                    f"Order #{o['order_id']}\nCurrent Stage: {latest['stage']} (updated: {latest['updated_at']})\nNotes        : {latest['comment'] or '-'}"
                )
            else:
                blocks.append(f"Order #{o['order_id']}\nCurrent Stage: -\nNotes        : -")
        return "\n\n".join(blocks)

    # If user asked for full details (or intent ambiguous) -> full block
    for o in orders:
        blocks.append(format_order_block(o, include_stage=True))

    return "\n\n".join(blocks)

# -- Main entrypoint --
# -- Main entrypoint --
# -- Main entrypoint --
def process_message(user_payload: dict, text: str) -> dict:
    """
    user_payload: JWT payload with at least agent_id, email, name
    text: user message
    returns: dict { "ok": bool, "text": str }
    """
    agent_id = user_payload.get("agent_id") if user_payload else None
    user_name = user_payload.get("name") if user_payload else "Unknown"

    # Log raw query
    logger.info("User(%s|%s) query: %s", agent_id, user_name, text)

    try:
        # --- Immediate "who am i" handling ---
        if re.search(r'\b(who am i|who am i\?|what is my name|my name)\b', text, flags=re.I):
            return {"ok": True, "text": f"You are {user_name} (agent_id: {agent_id})."}

        # quick gibberish/greeting detection
        if is_gibberish_or_greeting(text):
            help_text = (
                "I dont understand what you are talking about kindly refer to the documentation for the "
                "kind of query I accept."
            )
            return {"ok": True, "text": help_text}
        
            # LIST queries (employees / customers)
        if re.search(r'\b(show all employees|list employees|all employees|employees list)\b', text, flags=re.I):
            reply = handle_list_employees()
            logger.info("Reply list employees to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
            return {"ok": True, "text": reply}

        if re.search(r'\b(show all customers|list customers|all customers|customers list)\b', text, flags=re.I):
            reply = handle_list_customers()
            logger.info("Reply list customers to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
            return {"ok": True, "text": reply}

        # FIRST: check for explicit "payment received for <customer>" (customer-specific payments)
        m_customer_payment = re.search(r'\b(payment received for|payments for|payment for)\b', text, flags=re.I)
        if m_customer_payment:
            # try to extract customer name; if present call customer payment handler
            cust = extract_customer_name(text)
            if cust:
                reply = handle_customer_payment_query(agent_id, text)
                logger.info("Reply to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
                return {"ok": True, "text": reply}
            # else continue — fall back to generic payment handling

        # SECOND: payment intent? (agent's payments)
        if PAYMENT_KEYWORDS.search(text):
            # if text also contains words like "for" and a name, prefer customer handler
            possible_name = extract_customer_name(text)
            if possible_name and re.search(r'\b(for|of|customer)\b', text, flags=re.I):
                # explicit 'for' or 'of' with a name → treat as customer-specific
                reply = handle_customer_payment_query(agent_id, text)
                logger.info("Reply (customer payments) to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
                return {"ok": True, "text": reply}

            # otherwise generic payments for the agent
            reply = handle_payment_query(agent_id, text)
            logger.info("Reply to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
            return {"ok": True, "text": reply}

        # THIRD: order / customer queries (project info, sizes, stages)
        # Only attempt order lookup if message contains order-related keywords
        if re.search(r'\b(order|project|system size|system size for|deal date|deal date for|current stage|stage for|status|customer)\b', text, flags=re.I):
            name = extract_customer_name(text)
            if not name:
                # user mentioned orders but we couldn't identify a name -> helpful prompt
                return {"ok": True, "text": "I couldn't identify the customer name in your message. Try: 'Show project details for customer Rahul Sharma'."}
            reply = handle_order_query(text)
            logger.info("Reply to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
            return {"ok": True, "text": reply}

        # final fallback: the gibberish message you requested
        help_text = (
            "I dont understand what you are talking about kindly refer to the documentation for the "
            "kind of query I accept."
        )
        return {"ok": True, "text": help_text}

    except Exception as e:
        # Log exception details for debugging
        logger.exception("Error processing message for user %s: %s", agent_id, e)
        return {"ok": False, "text": "Internal server error while processing your request."}
