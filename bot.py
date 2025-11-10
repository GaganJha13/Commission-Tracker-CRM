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
    - Accepts patterns like:
        "project details for Rahul Sharma"
        "project details for customer Rahul Sharma"
        "complete status of Deepak"
        "payment received for Rahul Sharma"
        "Complete status for Amit Singh"
    - Strips common leading tokens like 'customer', 'mr', 'ms', 'mrs'.
    Returns cleaned name or None.
    """
    text = text.strip()

    # common patterns to try (ordered)
    patterns = [
        r'(?:project details(?:\s+for)?|show project details(?:\s+for)?|project for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:what is the system size for|system size for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:current stage for order of|current stage for|current stage of)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:payment received for|payments for|payment for)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:complete status for|complete status of|complete status)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'(?:order of|order for|order)\s+(?:customer\s+)?([A-Za-z][A-Za-z\s]+)',
        r'customer\s+([A-Za-z][A-Za-z\s]+)',
        r'([A-Za-z][A-Za-z\s]+)'  # fallback: any name-like token (last resort)
    ]

    for patt in patterns:
        m = re.search(patt, text, flags=re.I)
        if m:
            name = m.group(1).strip()
            # strip leading honorifics or noise words if present
            name = re.sub(r'^(customer|mr|mrs|ms|miss|dr)\s+', '', name, flags=re.I)
            name = re.sub(r'\s+', ' ', name).strip()
            # if name has trailing words like 'please' remove them (simple)
            name = re.sub(r'\b(please|now|today)\b', '', name, flags=re.I).strip()
            name = re.sub(r'^(for|of)\s+', '', name, flags=re.I)
            # ensure minimum length
            if len(name) >= 2:
                return name
    return None

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
    dates = parse_date_range_from_text(text)
    if not dates:
        # default: show last 30 days if not specified
        end = datetime.utcnow().date()
        start = end - timedelta(days=30)
        dates = (start.isoformat(), end.isoformat())

    start_date, end_date = dates
    rows, total = fetch_payouts_for_agent(agent_id, start_date, end_date)

    if not rows:
        return f"No payouts found for the period {start_date} to {end_date}."

    # format the response
    lines = []
    lines.append(f"Total payout amount between {start_date} and {end_date}: ₹{total:,.2f}")
    lines.append("")  # blank line
    idx = 1
    for r in rows:
        order_ref = f"Order #{r['order_id']}" if r['order_id'] else "(No Order)"
        paid_date = r['submitted_date']
        payment_type = r['payment_type']
        amount = float(r['amount'])
        # try to get customer name for order if available
        customer = None
        if r['order_id']:
            # lightweight fetch
            try:
                conn = get_db_connection()
                o = conn.execute("SELECT customer_name FROM orders WHERE order_id = ?", (r['order_id'],)).fetchone()
                if o:
                    customer = o["customer_name"]
            finally:
                conn.close()
        cust_text = customer if customer else "-"
        lines.append(f"{idx}) {payment_type} - ₹{amount:,.2f} - {order_ref} - {cust_text} - {paid_date} ")
        idx += 1

    return "\n".join(lines)

def handle_customer_payment_query(agent_id: int, text: str) -> str:
    # extract customer name
    match = re.search(r'customer\s+(.+)', text, re.IGNORECASE)
    if not match:
        return "Please specify a customer name."

    customer_name = extract_customer_name(text)
    if not customer_name:
        return "Please specify a customer name."

    conn = get_db_connection()
    try:
        # Find orders for this customer
        order = conn.execute("SELECT order_id FROM orders WHERE customer_name LIKE ?", (f"%{customer_name}%",)).fetchone()
        if not order:
            order = conn.execute("SELECT order_id FROM orders WHERE customer_name LIKE ? LIMIT 1", (f"%{customer_name}%",)).fetchone()
            if not order:
                return f"No orders found for customer matching '{customer_name}'."

        order_id = order["order_id"]
        payouts = conn.execute("SELECT amount, payment_type, submitted_date FROM payout_submitted WHERE order_id = ?", (order_id,)).fetchall()

        if not payouts:
            return f"No payouts found for customer {customer_name}."

        total = sum([float(p["amount"]) for p in payouts])
        lines = [f"Total payments received for {customer_name}: ₹{total:,.2f}"]
        lines.append("")
        for idx, p in enumerate(payouts, start=1):
            lines.append(f"{idx}) {p['payment_type']} - ₹{p['amount']:,.2f} - {p['submitted_date']}")

        return "\n".join(lines)
    finally:
        conn.close()


def handle_order_query(text: str) -> str:
    name = extract_customer_name(text)
    if not name:
        return "I couldn't identify the customer name in your message. Try: 'Show project details for customer Rahul Sharma'."

    orders = find_orders_by_customer_name(name)
    if not orders:
        return f"No orders found for customer matching '{name}'."

    parts = []
    for o in orders:
        parts.append(f"Order #{o['order_id']} — Customer: {o['customer_name']}, System Size: {o['system_size_kw']} kW, Deal Date: {o['deal_close_date']}")
        latest = fetch_latest_stage_for_order(o['order_id'])
        if latest:
            parts.append(f"Current Stage: {latest['stage']} (updated: {latest['updated_at']}) — Notes: {latest['comment'] or '-'}")
        else:
            parts.append("No stage updates found for this order.")
        parts.append("")  # blank line between orders

    return "\n".join(parts).strip()

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
        name = extract_customer_name(text)
        if name:
            reply = handle_order_query(text)
            logger.info("Reply to user %s: %s", agent_id, (reply.splitlines()[0] if reply else "<empty>"))
            return {"ok": True, "text": reply}

        # fallback help message
        help_text = (
            "Sorry, I didn't understand that. Examples I support:\n"
            " - Show my payments this month\n"
            " - Payments between 2025-01-10 and 2025-01-25\n"
            " - Show project details for customer Rahul Sharma\n"
            " - What is the system size for customer Deepak?\n"
        )
        return {"ok": True, "text": help_text}

    except Exception as e:
        # Log exception details for debugging
        logger.exception("Error processing message for user %s: %s", agent_id, e)
        return {"ok": False, "text": "Internal server error while processing your request."}
