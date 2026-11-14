# ☀️ Mini Solar Sales CRM

A lightweight **Solar Sales CRM** built for solar panel companies to manage agents, projects, payouts, and project stages — with a conversational chatbot interface for instant answers.

---

## ✨ Overview

This CRM helps sales teams track deals from closure to PTO (Permission to Operate), manage commissions accurately, and query data conversationally without digging through spreadsheets.

**Core focus areas:**
- Agents (Closers & Setters)
- Orders / Projects
- Payouts & Commissions
- Project Stage Tracking
- Conversational Chatbot

---

## 🖼️ Screenshots

### Login Screen
![Login Screen](image/capture2.png)

### Chatbot Interface
![Chatbot Interface](image/capture1.png)

---

## 🗂️ Key Components

### 1. Database Schema

| Table | Purpose |
|-------|---------|
| `user_employees` | Agent/employee info including roles (Closers, Setters) |
| `orders` | Project details — customer info, system size, closing agent |
| `payout_submitted` | Commissions, advances, and other payment types |
| `orders_stage` | Progress tracking from Project Acceptance → PTO with comments & timestamps |

### 2. Chatbot Application

- Built with **Python** (CLI or Flask Web UI)
- Backed by **SQLite / MySQL**
- Secure login with **hashed passwords**
- Natural language queries for payments, project status, and more

### 3. Security & Logging

- Parameterized SQL queries (SQL injection protection)
- Passwords hashed with bcrypt
- Query logging for auditing and troubleshooting

### 4. Bonus Features (Optional)

- JWT-based authentication for API usage
- Web deployment of the chatbot UI

---

## 🔐 Login Details

| User    | Email                 | Password     |
|---------|-----------------------|--------------|
| Alice   | alice@example.com     | alicepass    |
| Bob     | bob@example.com       | bobpass      |
| Charlie | charlie@example.com   | charliepass  |

---

## 💬 Accepted Queries by Bot

### Identity / Helpers
- `Who am I`

### Payments / Payouts
- `Payments between 2025-01-10 and 2025-01-25`
- `Payments this week`
- `Payments last week`
- `Payments for customer Rahul Sharma`
- `Payment received for customer Rahul Sharma`

### Lists
- `Show all employees`
- `Show all customers`

### Order / Project Queries
- `Show project details for customer Rahul Sharma`
- `Complete status for Rahul Sharma`
- `What is the system size for customer Rahul?`
- `What is the deal date for customer Rahul?`
- `Current stage for order of Amit Singh?`

---

## 🚀 How This CRM Helps a Solar Panel Company

### Streamlined Sales Management
Agents track leads and orders in one place. Centralized data reduces miscommunication and lost records.

### Agent Performance Tracking
Payout and commission tracking lets managers measure performance and calculate accurate payouts based on deal stages.

### Project Status Transparency
Tracks projects from acceptance → PTO. Highlights orders on Hold, in Permitting, or pending Inspection.

### Faster Query Resolution
Chatbot lets agents ask about payments or project status in plain language — no spreadsheet hunting required.

### Financial Accuracy
Supports multiple payout types (M1, M2, ADVANCE, CLAWBACK) to keep finance teams accurate.

### Decision Support
Managers can review cumulative sales, outstanding orders, and payouts for clearer insights.

### Enhanced Agent Experience
Simple login + conversational interface means a low learning curve and instant answers.

### Audit & Compliance Ready
Query logs and hashed passwords support accountability and data security.

---

## 📖 Example Scenario

Imagine an agent named **Rahul**:

- He closed 3 solar projects this month.
- He wants to know his total payout for the last week.
- Instead of calling the manager or checking Excel, he types:

Show my payments last week

**Bot responds:**

Total Payout = ₹85,000

M1     - ₹30,000 - Order #123 - Customer Name 1
M2     - ₹40,000 - Order #110 - Customer Name 2
Advance - ₹15,000 - (No Order)

Text
Rahul now knows exactly how much he has earned — instantly.

---

## 📌 Summary

This CRM improves **efficiency, transparency, and accountability** while empowering agents and managers to make faster, data-driven decisions.

---

<p align="center">
  <strong>Built for solar sales teams who want clarity without complexity.</strong>
</p>