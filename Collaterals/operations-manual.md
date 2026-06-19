# AlgoWorkforce — Operations Manual
**Version 1.0 | AI-Powered Enterprise Workforce Platform**

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Getting Started & Login](#2-getting-started--login)
3. [Dashboard](#3-dashboard)
4. [Chat with AI Agents](#4-chat-with-ai-agents)
5. [Voice Console](#5-voice-console)
6. [Knowledge Base](#6-knowledge-base)
7. [Company & Agent Settings](#7-company--agent-settings)
8. [Analytics](#8-analytics)
9. [Human Escalations](#9-human-escalations)
10. [Integrations](#10-integrations)
11. [Admin Panel](#11-admin-panel)
12. [Workflows](#12-workflows)
13. [Audit Logs](#13-audit-logs)
14. [Troubleshooting Guide](#14-troubleshooting-guide)
15. [Frequently Asked Questions](#15-frequently-asked-questions)

---

## 1. Platform Overview

**AlgoWorkforce** is an enterprise AI workforce platform where every department in your organisation has a dedicated AI agent that can:

- Answer customer and employee questions instantly — 24 hours a day, 7 days a week
- Hold natural voice conversations (speak and listen like a real assistant)
- Transfer conversations between departments automatically
- Learn from your company documents via the Knowledge Base
- Escalate to a human operator when needed
- Speak multiple languages including Indian languages, Singlish, and more

### Departments Available

| Agent | Role |
|-------|------|
| **Receptionist** | First point of contact, greets callers, routes to departments |
| **Customer Care** | Handles support queries, complaints, and follow-ups |
| **Sales** | Product information, pricing, demos, lead qualification |
| **HR** | Leave policies, onboarding, employee queries |
| **Finance** | Invoices, payment queries, financial reports |
| **IT Support** | Technical help, troubleshooting, ticket creation |
| **Marketing** | Campaign info, brand queries, content guidance |

---

## 2. Getting Started & Login

### Accessing the Platform

Open your browser and go to:
- **Live (VPS):** https://www.algoworkforce.com
- **Local (Docker):** http://localhost:3200

### Login Credentials

| Role | Username | Default Password |
|------|----------|-----------------|
| Admin | `admin` | `admin123` |
| Agent | `agent` | `agent123` |

> **Security tip:** Change default passwords immediately after first login via Settings → Profile.

### First Login Checklist

- [ ] Log in as Admin
- [ ] Go to **Settings → Company & Agents** — enter your company name, tagline, and greeting script
- [ ] Go to **Knowledge Base** — upload your product catalog, FAQ, and policies
- [ ] Test a chat conversation with the Sales agent
- [ ] Test a voice call with the Receptionist

---

## 3. Dashboard

The Dashboard is your command centre. It shows:

- **Active sessions** — how many conversations are happening right now
- **Total conversations today** — chat + voice combined
- **Agent utilisation** — which agents are busiest
- **Escalations pending** — conversations waiting for a human operator
- **Quick actions** — jump to any module in one click

### Navigation Sidebar

```
Dashboard
Chat
Voice Console
Knowledge Base
Analytics
Escalations
Workflows
Integrations
Audit Logs
Settings
Admin (admin only)
```

---

## 4. Chat with AI Agents

### Starting a Chat

1. Click **Chat** in the left sidebar
2. Select a department from the agent selector (top of the page)
3. Type your message in the input box at the bottom
4. Press **Enter** or click **Send**

The agent responds within 2–5 seconds using your Knowledge Base + OpenAI GPT-4.

### Transferring Between Departments

Type naturally in chat, e.g.:
- _"Can you transfer me to Sales?"_
- _"I need to speak with HR"_
- _"Connect me to the Finance team"_

The system detects the intent and switches you to the correct department agent automatically.

### Chat Features

| Feature | How to Use |
|---------|-----------|
| **Context memory** | The agent remembers previous messages in the same session |
| **Knowledge Base** | Agents automatically search KB documents for every response |
| **File upload** | Click the paperclip icon to upload images or documents during chat |
| **Markdown rendering** | Responses support bold, bullets, tables, and code blocks |
| **New conversation** | Click the **+** button to start a fresh session |

### Tips for Better Chat Responses

- Be specific: _"What is the pricing for the Professional plan?"_ beats _"tell me about prices"_
- Ask follow-ups naturally — the agent remembers context within the session
- If the agent seems to give generic answers, upload more documents to the Knowledge Base

---

## 5. Voice Console

The Voice Console lets you have a real spoken conversation with any AI agent.

### Starting a Voice Call

1. Click **Voice Console** in the sidebar
2. Select a department (e.g. **Receptionist**)
3. Allow microphone access when the browser asks
4. Choose your input mode:
   - **Auto-detect** — AI listens continuously and responds when you pause
   - **Push to Talk** — hold the mic button while speaking, release to get a response
5. The agent will greet you automatically

### Language Selection

Use the **Language** dropdown in the voice console sidebar to choose:

| Language | Code | Notes |
|----------|------|-------|
| English (default) | en | Best accuracy |
| Hindi | hi | Full support |
| Tamil | ta | Full support |
| Telugu | te | Full support |
| Kannada | kn | Full support |
| Malay | ms | Singlish-friendly |
| Mandarin / Hokkien | zh | Hokkien maps to Mandarin |
| Auto-detect | auto | Detects language, may be slower |

> **Note:** Auto-detect is sensitive to background noise. Use a specific language for best results.

### Transferring Calls by Voice

During a voice call, say naturally:
- _"Transfer me to Sales please"_
- _"I need to speak with HR"_
- _"Can you connect me to Finance?"_

The system:
1. Detects the transfer intent
2. Announces the transfer
3. Switches the active agent and continues the call
4. The new agent greets you with its persona

### Voice Console Controls

| Button | Action |
|--------|--------|
| Mic icon (Push-to-Talk) | Hold to speak |
| **Auto-detect toggle** | Switch to hands-free mode |
| **End Call** | Terminate session and save transcript |
| **Volume slider** | Adjust agent voice volume |

### Voice Quality Tips

- Use headphones to avoid echo
- Speak clearly and at a normal pace
- Avoid background music or TV
- If the agent mishears, simply repeat or rephrase

---

## 6. Knowledge Base

The Knowledge Base is how agents learn about your company, products, and policies.

### Uploading Documents

1. Click **Knowledge Base** in the sidebar
2. In the **Upload Document** panel:
   - **Title** (optional) — e.g. "Product Catalog Q3"
   - **Category** — match the agent that should use it (Sales, HR, Finance, etc.)
   - **File** — select your file
3. Click **Upload**
4. Wait for the status badge to show **complete** (10–60 seconds)

### Supported File Types

| Format | Use For |
|--------|---------|
| `.txt` | Plain product lists, FAQs, scripts |
| `.md` | Formatted documentation |
| `.pdf` | Brochures, manuals, reports |
| `.docx` | Word documents |
| `.csv` | Data tables, product pricing |
| `.json` | Structured data |

### Recommended File Structure

```
products-catalog.txt      → Category: Sales
pricing-guide.txt         → Category: Sales
hr-policies.txt           → Category: HR
leave-policy.txt          → Category: HR
faq-customer.txt          → Category: Support
company-overview.txt      → Category: General
finance-faq.txt           → Category: Finance
it-support-guide.txt      → Category: IT
marketing-kit.txt         → Category: Marketing
```

### Searching the Knowledge Base

1. Click the **Semantic Search** tab
2. Type a question in natural language (e.g. _"What is the refund policy?"_)
3. The system returns the most relevant passages with match scores

### Best Practices

- Keep each document focused on one topic
- Use clear headings and bullet points
- Include product names, prices, and descriptions explicitly
- Re-upload whenever information changes (delete the old version first)
- Documents stuck on `pending` for more than 2 minutes — delete and re-upload

---

## 7. Company & Agent Settings

### Accessing Settings

Click the **Settings** (gear icon) → **Company & Agents** tab

### Company Branding

| Field | Description | Example |
|-------|-------------|---------|
| Company Name | Spoken in every greeting | "AlgoWorkforce" |
| Tagline | Company positioning | "Your AI Enterprise Workforce" |
| Website | Shared in conversations when asked | "www.algoworkforce.com" |
| Default Greeting Script | What Receptionist says when call starts | "Hello, this is {agent_name} from AlgoWorkforce. How may I assist you today?" |

> Use `{agent_name}` as a placeholder — it auto-fills with the actual agent's name.

### Per-Agent Personas

For each department agent you can customise:

| Setting | Description |
|---------|-------------|
| **Display Name** | What the agent calls itself (e.g. "Alex from Sales") |
| **Persona / Script** | Specific instructions for this agent (tone, topics to cover) |

**Example Sales agent script:**
```
You are Alex, Senior Sales Consultant at AlgoWorkforce. Your role is to 
help prospects understand our AI workforce solutions, provide pricing, 
and book demos. Always be enthusiastic, professional, and customer-first.
Reference our product catalog when answering questions. If asked about 
enterprise pricing, offer to schedule a call with our team.
```

### API Keys (Settings → Integrations)

| Key | Purpose |
|-----|---------|
| `OPENAI_API_KEY` | Powers all AI responses and voice transcription |
| `ELEVENLABS_API_KEY` | Natural-sounding voice responses (TTS) |
| `RESEND_API_KEY` | Email notifications for escalations |

---

## 8. Analytics

The Analytics page shows conversation and performance data.

### Metrics Available

- **Total conversations** by day/week/month
- **Conversations by department** — which agents are most active
- **Average response time** — AI latency per agent
- **Voice vs Chat split** — usage channel breakdown
- **Escalation rate** — % of conversations escalated to humans
- **Knowledge Base hit rate** — how often KB is referenced

### Exporting Data

Click **Export CSV** to download raw conversation logs for reporting.

---

## 9. Human Escalations

When an agent cannot resolve a query, it escalates to a human operator.

### Triggers for Escalation

- User says _"I want to speak to a real person"_
- Agent detects high frustration or repeated failed attempts
- Query is outside the agent's scope (legal, medical, etc.)
- User explicitly requests escalation

### Handling Escalations

1. Click **Escalations** in the sidebar
2. You'll see a list of open escalations with:
   - Customer name / session ID
   - Department agent that escalated
   - Reason for escalation
   - Full conversation transcript
3. Click an escalation to view details
4. Use the **Reply** field to respond to the customer
5. Mark as **Resolved** when complete

---

## 10. Integrations

### Available Integrations

| System | What It Does |
|--------|-------------|
| **CRM (Salesforce / HubSpot)** | Sales agent can look up and update contacts |
| **HRIS (Workday / BambooHR)** | HR agent accesses employee records |
| **Accounting (QuickBooks / Xero)** | Finance agent looks up invoices |
| **Ticketing (Jira / Zendesk)** | IT agent creates and tracks support tickets |
| **Email (Resend)** | Sends escalation and notification emails |
| **Phone (Twilio)** | Connect the platform to a real phone number |

### Setting Up an Integration

1. Go to **Settings → Integrations**
2. Click the integration card
3. Enter the API key / credentials
4. Click **Test Connection** to verify
5. The agent will automatically use the integration during conversations

### Connecting a Phone Line (Twilio)

1. Create a Twilio account at twilio.com
2. Purchase a phone number
3. Add to `.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxx
   TWILIO_PHONE_NUMBER=+1234567890
   ```
4. Set your Twilio webhook to: `https://www.algoworkforce.com/api/v1/voice/twilio`
5. Callers will now reach your Receptionist AI agent

---

## 11. Admin Panel

The Admin panel is visible only to users with the **Admin** role.

### User Management

1. Click **Admin** in the sidebar
2. **Users tab** — create, edit, disable users
3. Roles: `admin`, `agent`, `user`

### Creating a New User

1. Click **Add User**
2. Fill in username, email, role, and password
3. Click **Save**
4. Share credentials with the new user

### System Settings

- View all active sessions
- Force-expire JWT tokens (emergency logout)
- View system health indicators

---

## 12. Workflows

Workflows automate multi-step processes triggered by conversation events.

### Example Workflows

| Workflow | Trigger | Action |
|----------|---------|--------|
| Lead capture | Sales chat ends | Save to CRM |
| Support ticket | IT agent conversation | Create Jira ticket |
| Leave request | HR detects leave intent | Draft leave form |
| Follow-up email | Sales demo requested | Schedule email via Resend |

### Creating a Workflow (coming in next release)

Workflow builder is currently in development. For now, workflows are configured via the `.env` settings and agent scripts.

---

## 13. Audit Logs

The Audit Logs page shows a complete history of:

- User logins and logouts
- API key changes
- Knowledge Base uploads and deletions
- Agent settings changes
- Escalations created and resolved

### Filtering Logs

- Filter by date range
- Filter by user
- Filter by action type
- Export to CSV

---

## 14. Troubleshooting Guide

### Login Issues

**Problem:** Cannot log in with admin/agent credentials
**Solution:**
1. Ensure the backend API is running: `docker compose ps`
2. Check API health: visit `http://localhost:8080/api/v1/health`
3. Default credentials: `admin` / `admin123` or `agent` / `agent123`
4. If still failing, reset via: `docker compose exec api python scripts/seed_users.py`

---

**Problem:** "401 Unauthorized" errors in Settings or KB
**Solution:**
1. Log out and log back in to refresh your JWT token
2. JWT tokens expire after 8 hours — re-login is required

---

### Knowledge Base Issues

**Problem:** Documents stay on "pending" after upload
**Solution:**
1. Check API logs: `docker compose logs api --tail=50`
2. Check ChromaDB is running: `docker compose ps chroma`
3. Delete the stuck document and re-upload
4. Ensure the file contains extractable text (scanned PDFs without OCR will fail)

**Problem:** Agents don't reference uploaded documents
**Solution:**
1. Verify document shows **complete** status in KB page
2. Use **Semantic Search** tab to test if the document is findable
3. Ensure you uploaded to the correct **Category** matching the agent's department
4. Ask a very specific question — generic questions may not trigger retrieval

---

### Voice Issues

**Problem:** No audio / agent not speaking
**Solution:**
1. Check `ELEVENLABS_API_KEY` is set in `.env`
2. Check browser microphone permissions (click lock icon in browser address bar)
3. Try a different browser (Chrome recommended)

**Problem:** Agent speaks in wrong language
**Solution:**
1. Select your language explicitly from the Language dropdown — don't use Auto
2. Background TV/music can confuse auto-detection

**Problem:** Voice transfer doesn't complete
**Solution:**
1. Say the department name clearly: _"Transfer me to Sales"_
2. Wait 3–5 seconds after speaking before the transfer initiates
3. If issue persists, use Chat to transfer instead

---

### Chat Issues

**Problem:** Chat not responding
**Solution:**
1. Check `OPENAI_API_KEY` is set in `.env`
2. Verify API is running at `http://localhost:8080/api/v1/health`
3. Check OpenAI account has available credits

**Problem:** Agents give generic answers ignoring company info
**Solution:**
1. Upload your product/policy documents to Knowledge Base with correct category
2. Wait for status to show **complete**
3. Ask specific questions that match the document content

---

### Docker / Deployment Issues

**Problem:** App not loading after restart
**Solution:**
```bash
cd /root/enterprise-ai-workforce
docker compose down
docker compose up -d --build
docker compose logs -f api
```

**Problem:** Knowledge Base data lost after restart
**Solution:** This was a known bug (volume mount path). Ensure your `docker-compose.yml` has:
```yaml
chroma:
  volumes:
    - chroma_data:/chroma/chroma
  environment:
    - IS_PERSISTENT=TRUE
    - CHROMA_SERVER_PERSIST_PATH=/chroma/chroma
```

**NEVER use `docker compose down -v`** — the `-v` flag deletes all data volumes.

---

## 15. Frequently Asked Questions

**Q: How do I change the company name the agent uses when greeting?**
Go to Settings → Company & Agents → enter your Company Name and Greeting Script. Changes take effect on the next conversation.

**Q: Can I add my own custom agents?**
Currently the 7 departments are fixed. Custom agent personas (name, script, tone) can be set per-department via Settings → Company & Agents.

**Q: Is data secure? Who can see my conversations?**
All data is stored in your own database on your VPS. AlgoWorkforce does not have access to your conversations. OpenAI processes text for AI responses per their privacy policy.

**Q: Can multiple users log in at the same time?**
Yes. The platform supports multiple concurrent users. Each session is independent.

**Q: How do I connect the app to a real phone number?**
See Section 10 — Integrations — Twilio setup. You need a Twilio account and phone number.

**Q: My agent keeps introducing itself on every message. How do I fix this?**
The agent script in Settings → Company & Agents controls introduction behavior. Remove the greeting from the script if you only want it on the first message.

**Q: What languages are supported?**
English, Hindi, Tamil, Telugu, Kannada, Bengali, Malay, Mandarin, and more via the voice console Language selector. Chat works in any language OpenAI supports.

**Q: How do I back up my data?**
```bash
# On VPS — dump PostgreSQL
docker compose exec postgres pg_dump -U workforce workforce > backup_$(date +%Y%m%d).sql
```

---

*For technical support, contact the AlgoWorkforce team at support@algoworkforce.com*
*Platform version: 1.0 | Last updated: June 2026*
