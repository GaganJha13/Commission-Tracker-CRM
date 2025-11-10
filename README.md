# Mini Solar Sales CRM

## Project Overview

This project is a **Solar Sales CRM system** designed to help a solar panel company manage its sales operations efficiently. The CRM focuses on **agents (salespeople)**, **orders/projects**, **payouts**, and **project stages**, while providing a **chatbot interface** for conversational querying.

---

## Key Components

### 1. Database Schema

- **user_employees** – Stores agent/employee information including roles like Closers and Setters.  
- **orders** – Stores project details such as customer info, system size, and the agent who closed the deal.  
- **payout_submitted** – Tracks agent commissions, advances, and other payment types.  
- **orders_stage** – Tracks each order’s progress from Project Acceptance → PTO (Permission to Operate) with comments and timestamps.  

### 2. Chatbot Application

- Built using **Python** (CLI or Flask Web UI) with **SQLite/MySQL** database.  
- Provides **login functionality** for agents with **hashed passwords** for security.  
- Agents can ask conversational queries such as:  
  - Payment queries: `"Show my payments this month"`  
  - Order/project details: `"Show project details for customer Rahul Sharma"`  
  - Current stage updates for orders: `"Current stage for order of Amit Singh?"`  
- Bot responds with aggregated totals, tables, or order details.

### 3. Security & Logging

- SQL queries are **parameterized** to prevent SQL injection.  
- Passwords are **hashed** using a library like bcrypt.  
- System maintains **logs of queries** for auditing and troubleshooting.

### 4. Bonus (Optional)

- JWT-based authentication for secure API usage.  
- Web deployment of the chatbot UI for real-time access.

---

## How This CRM Helps a Solar Panel Company

### Streamlined Sales Management
- Agents can track all their leads and orders in one system.  
- Sales data is centralized, preventing miscommunication and lost records.

### Agent Performance Tracking
- Payout and commission tracking allows managers to measure agent performance.  
- Helps in calculating accurate payouts based on deal closure stages.

### Project Status Transparency
- Tracks projects from acceptance → PTO, giving real-time status updates.  
- Reduces delays by highlighting orders that are on Hold, in Permitting, or pending Inspection.

### Faster Query Resolution
- Chatbot interface allows agents to quickly query payments or project status conversationally.  
- No need to manually sift through spreadsheets or databases.

### Financial Accuracy
- Tracks multiple types of payouts like M1, M2, ADVANCE, CLAWBACK.  
- Helps finance teams avoid errors and discrepancies in payouts.

### Decision Support
- Managers can analyze cumulative sales, outstanding orders, and payouts easily.  
- Provides actionable insights such as which projects are delayed or which agents are performing best.

### Enhanced Agent Experience
- Simple login + conversational bot reduces learning curve.  
- Agents can get instant responses to queries about their payments or projects.

### Audit & Compliance Ready
- Query logs and secure storage of sensitive information (like hashed passwords) ensures accountability and data security.

---


## Example Scenario

Imagine an agent named **Rahul**:

- He closed 3 solar projects this month.  
- He wants to know his total payout for the last week.  
- Instead of calling the manager or checking Excel, Rahul types in:

Show my payments last week

- The bot instantly responds:

Total Payout = ₹85,000
1) M1 - ₹30,000 - Order #123 - Customer Name 1
2) M2 - ₹40,000 - Order #110 - Customer Name 2
3) Advance - ₹15,000 - (No Order)

Rahul now knows exactly how much he has earned without manual calculation.

---

## Summary

This CRM improves **efficiency, transparency, and accountability** while empowering agents and managers to make faster, data-driven decisions.
