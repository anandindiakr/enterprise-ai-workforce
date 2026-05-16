/**
 * AI Workforce Platform – User Manual Generator
 * Produces a polished Word document with cover page, TOC, and screenshot sections.
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, Header, Footer, HeadingLevel, AlignmentType, PageBreak,
  BorderStyle, WidthType, ShadingType, TableOfContents, LevelFormat,
  VerticalAlign, PageNumber,
} = require('docx');
const fs = require('fs');
const path = require('path');

// ─── helpers ──────────────────────────────────────────────────────────────────
const SHOTS = path.join(__dirname, '..', 'tests', 'e2e', 'screenshots');
const OUT    = path.join(__dirname, 'AI_Workforce_Platform_User_Manual.docx');

const PAGE_W  = 12240;  // US Letter 8.5"
const PAGE_H  = 15840;
const MARGIN  = 1080;   // 0.75"
const BODY_W  = PAGE_W - MARGIN * 2;  // 10,080 DXA ≈ 7"

const AMBER   = 'F59E0B';
const DARK_BG = '0F172A';
const MID_BG  = '1E293B';
const WHITE   = 'FFFFFF';
const LIGHT   = 'CBD5E1';
const MUTED   = '64748B';

const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: '334155' };
const allBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
const noBorder   = { style: BorderStyle.NIL };
const noBorders  = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function img(name, { w = BODY_W, h } = {}) {
  const p = path.join(SHOTS, name);
  if (!fs.existsSync(p)) {
    return new Paragraph({ spacing: { before: 60, after: 60 }, children: [new TextRun({ text: `[Screenshot: ${name}]`, font: 'Arial', size: 18, color: MUTED, italics: true })] });
  }
  const data = fs.readFileSync(p);
  const height = h ?? Math.round(w * 9 / 16);
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    children: [new ImageRun({ type: 'png', data, transformation: { width: w, height }, altText: { title: name, description: name, name } })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 160 },
    children: [new TextRun({ text, font: 'Arial', size: 36, bold: true, color: AMBER })],
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 280, after: 120 },
    children: [new TextRun({ text, font: 'Arial', size: 28, bold: true, color: WHITE })],
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 200, after: 80 },
    children: [new TextRun({ text, font: 'Arial', size: 24, bold: true, color: LIGHT })],
  });
}
function body(text, { bold = false, color = LIGHT, size = 22 } = {}) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text, font: 'Arial', size, color, bold })],
  });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: 'bullets', level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, font: 'Arial', size: 22, color: LIGHT })],
  });
}
function step(n, text) {
  return new Paragraph({
    numbering: { reference: 'steps', level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, font: 'Arial', size: 22, color: LIGHT })],
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 40, after: 160 },
    children: [new TextRun({ text, font: 'Arial', size: 18, color: MUTED, italics: true })],
  });
}
function spacer(before = 200) {
  return new Paragraph({ spacing: { before, after: 0 }, children: [new TextRun('')] });
}
function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}
function tip(text) {
  return new Table({
    width: { size: BODY_W, type: WidthType.DXA },
    columnWidths: [BODY_W],
    rows: [new TableRow({ children: [new TableCell({
      borders: allBorders,
      shading: { fill: '1C2A1A', type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 200, right: 200 },
      width: { size: BODY_W, type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun({ text: `💡 Tip:  ${text}`, font: 'Arial', size: 20, color: '86EFAC' })] })],
    })]})],
  });
}
function noteBox(text) {
  return new Table({
    width: { size: BODY_W, type: WidthType.DXA },
    columnWidths: [BODY_W],
    rows: [new TableRow({ children: [new TableCell({
      borders: allBorders,
      shading: { fill: '1A1E2A', type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 200, right: 200 },
      width: { size: BODY_W, type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun({ text: `📝 Note:  ${text}`, font: 'Arial', size: 20, color: '93C5FD' })] })],
    })]})],
  });
}

function deptRow(icon, name, color, desc, chatTools, voiceTools) {
  const cellW = [600, 1200, 3440, 2160, 1680];  // icon/name/desc/chat/voice = 9080
  return new TableRow({ children: [
    new TableCell({ borders: allBorders, width: { size: cellW[0], type: WidthType.DXA }, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: icon, font: 'Segoe UI Emoji', size: 26 })] })] }),
    new TableCell({ borders: allBorders, width: { size: cellW[1], type: WidthType.DXA }, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ children: [new TextRun({ text: name, font: 'Arial', size: 20, bold: true, color })] })] }),
    new TableCell({ borders: allBorders, width: { size: cellW[2], type: WidthType.DXA }, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ children: [new TextRun({ text: desc, font: 'Arial', size: 19, color: LIGHT })] })] }),
    new TableCell({ borders: allBorders, width: { size: cellW[3], type: WidthType.DXA }, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ children: [new TextRun({ text: chatTools, font: 'Arial', size: 18, color: '86EFAC' })] })] }),
    new TableCell({ borders: allBorders, width: { size: cellW[4], type: WidthType.DXA }, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, children: [new Paragraph({ children: [new TextRun({ text: voiceTools, font: 'Arial', size: 18, color: '93C5FD' })] })] }),
  ]});
}

// ─── document ────────────────────────────────────────────────────────────────
const HEADER_PAR = new Header({ children: [new Table({
  width: { size: BODY_W, type: WidthType.DXA },
  columnWidths: [BODY_W - 2000, 2000],
  rows: [new TableRow({ children: [
    new TableCell({ borders: noBorders, width: { size: BODY_W - 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'AI Workforce Platform  —  User Manual', font: 'Arial', size: 18, color: MUTED })] })] }),
    new TableCell({ borders: noBorders, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Confidential', font: 'Arial', size: 18, color: MUTED })] })] }),
  ]})]
})]});

const FOOTER_PAR = new Footer({ children: [new Table({
  width: { size: BODY_W, type: WidthType.DXA },
  columnWidths: [BODY_W - 1200, 1200],
  rows: [new TableRow({ children: [
    new TableCell({ borders: noBorders, width: { size: BODY_W - 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '© 2025 AI Workforce Platform', font: 'Arial', size: 16, color: MUTED })] })] }),
    new TableCell({ borders: noBorders, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: 'Page ', font: 'Arial', size: 16, color: MUTED }), new TextRun({ children: [PageNumber.CURRENT], font: 'Arial', size: 16, color: MUTED }), new TextRun({ text: ' of ', font: 'Arial', size: 16, color: MUTED }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: 'Arial', size: 16, color: MUTED })] })] }),
  ]})]
})]});

// Cover page (no header/footer)
const COVER_SECTION = {
  properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
  headers: { default: new Header({ children: [new Paragraph({ children: [] })] }) },
  footers: { default: new Footer({ children: [new Paragraph({ children: [] })] }) },
  children: [
    spacer(1800),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 80 }, children: [
      new TextRun({ text: '⚡', font: 'Segoe UI Emoji', size: 80 }),
    ]}),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 80 }, children: [
      new TextRun({ text: 'AI WORKFORCE PLATFORM', font: 'Arial', size: 60, bold: true, color: AMBER }),
    ]}),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 160 }, children: [
      new TextRun({ text: 'Complete User Manual', font: 'Arial', size: 32, color: LIGHT }),
    ]}),
    new Table({
      alignment: AlignmentType.CENTER,
      width: { size: 5000, type: WidthType.DXA },
      columnWidths: [5000],
      rows: [new TableRow({ children: [new TableCell({
        borders: allBorders,
        shading: { fill: MID_BG, type: ShadingType.CLEAR },
        margins: { top: 160, bottom: 160, left: 200, right: 200 },
        width: { size: 5000, type: WidthType.DXA },
        children: [
          new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Enterprise Multi-Agent AI Platform', font: 'Arial', size: 24, color: LIGHT })] }),
          new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '7 Departments  ·  Chat & Voice AI  ·  MCP Integrations', font: 'Arial', size: 20, color: MUTED })] }),
        ],
      })]})],
    }),
    spacer(600),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Version 1.0  |  May 2025', font: 'Arial', size: 20, color: MUTED })] }),
  ],
};

const MAIN_SECTION = {
  properties: { page: { size: { width: PAGE_W, height: PAGE_H }, margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN } } },
  headers: { default: HEADER_PAR },
  footers: { default: FOOTER_PAR },
  children: [
    // ── TOC ──────────────────────────────────────────────────────────────────
    h1('Table of Contents'),
    new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-3' }),
    pageBreak(),

    // ── 1. Introduction ──────────────────────────────────────────────────────
    h1('1. Introduction'),
    h2('What Is the AI Workforce Platform?'),
    body('The AI Workforce Platform is an enterprise-grade multi-agent AI system that gives any organization — from Fortune 500 companies to small startups — instant access to a complete AI-powered workforce. Seven specialized department agents handle requests via text chat or real-time voice, 24 hours a day, 7 days a week.'),
    body('Unlike a simple chatbot, the platform mimics a real company structure. A Director AI analyzes every request, routes it to the correct department, and coordinates between agents if multiple departments are needed.'),
    spacer(100),
    img('welcome_hero.png', { w: BODY_W, h: Math.round(BODY_W * 9/16) }),
    caption('Figure 1.1 — The platform\'s Welcome / Landing page'),
    spacer(100),

    h2('Who Should Use This Manual?'),
    body('This manual is written for:'),
    bullet('End Users — people who will chat or speak with the AI agents daily'),
    bullet('Team Managers — responsible for configuring department workflows'),
    bullet('IT Administrators — deploying, securing, and maintaining the platform'),
    bullet('Decision Makers — evaluating the platform for their organization'),
    spacer(100),

    h2('What Can It Do For Your Organization?'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.5), Math.round(BODY_W * 0.5)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: AMBER, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Enterprise', font: 'Arial', size: 22, bold: true, color: '000000' })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: AMBER, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'SMB / Startup', font: 'Arial', size: 22, bold: true, color: '000000' })] })] }),
        ]}),
        new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA }, children: [
            new Paragraph({ children: [new TextRun({ text: '✔ Replace tier-1 support queues', font: 'Arial', size: 20, color: LIGHT })] }),
            new Paragraph({ children: [new TextRun({ text: '✔ Automate HR intake & onboarding', font: 'Arial', size: 20, color: LIGHT })] }),
            new Paragraph({ children: [new TextRun({ text: '✔ Finance reporting on demand', font: 'Arial', size: 20, color: LIGHT })] }),
            new Paragraph({ children: [new TextRun({ text: '✔ 24/7 IT helpdesk coverage', font: 'Arial', size: 20, color: LIGHT })] }),
          ]}),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA }, children: [
            new Paragraph({ children: [new TextRun({ text: '✔ Operate like a 50-person team', font: 'Arial', size: 20, color: LIGHT })] }),
            new Paragraph({ children: [new TextRun({ text: '✔ Instant customer care', font: 'Arial', size: 20, color: LIGHT })] }),
            new Paragraph({ children: [new TextRun({ text: '✔ Sales pipeline on autopilot', font: 'Arial', size: 20, color: LIGHT })] }),
            new Paragraph({ children: [new TextRun({ text: '✔ Pay-as-you-scale cloud deploy', font: 'Arial', size: 20, color: LIGHT })] }),
          ]}),
        ]}),
      ],
    }),
    pageBreak(),

    // ── 2. Getting Started ───────────────────────────────────────────────────
    h1('2. Getting Started'),
    h2('System Requirements'),
    body('The platform is entirely browser-based. No installation is required for end users.'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.35), Math.round(BODY_W * 0.65)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.35), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Requirement', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.65), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Details', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['Browser',      'Chrome 100+, Firefox 100+, Edge 100+, Safari 16+'],
          ['Internet',     'Stable connection (Voice AI needs ≥ 1 Mbps upload)'],
          ['Microphone',   'Required for Voice Console only (grant permission when prompted)'],
          ['Speakers',     'Required for TTS (Text-to-Speech) responses'],
          ['Resolution',   '1280×720 minimum; 1440×900 or higher recommended'],
        ].map(([req, det]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.35), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: req, font: 'Arial', size: 20, bold: true, color: AMBER })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.65), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: det, font: 'Arial', size: 20, color: LIGHT })] })] }),
        ]}))),
      ],
    }),
    spacer(200),

    h2('Accessing the Platform'),
    body('Navigate to the platform URL in your browser. If you are not logged in, you will be redirected to the Welcome page.'),
    spacer(60),
    img('01_login_page_renders.png', { w: BODY_W, h: Math.round(BODY_W * 9/16) }),
    caption('Figure 2.1 — Login page (pre-filled with demo credentials)'),
    spacer(60),
    noteBox('Default demo credentials — Username: admin  |  Password: admin\nChange these immediately in the .env file before any production deployment.'),
    spacer(100),

    h2('Logging In — Step by Step'),
    step(1, 'Open your browser and go to http://localhost:4000 (or your deployment URL)'),
    step(2, 'You will be redirected to /welcome — click "Launch Platform" or "Sign In"'),
    step(3, 'Enter your username in the top field (default: admin)'),
    step(4, 'Enter your password in the bottom field (default: admin)'),
    step(5, 'Click the amber "Sign In" button — you will be redirected to the Dashboard'),
    step(6, 'Your session token is stored securely and persists across page refreshes'),
    spacer(100),
    img('05_login_success_dashboard.png', { w: BODY_W, h: Math.round(BODY_W * 9/16) }),
    caption('Figure 2.2 — The Dashboard after successful login showing all 7 departments online'),
    spacer(60),
    tip('The login form pre-fills with "admin" to make the demo easier. Clear both fields and type your real credentials when using a production account.'),
    pageBreak(),

    // ── 3. Dashboard ─────────────────────────────────────────────────────────
    h1('3. The Dashboard'),
    body('The Dashboard is your mission control. It displays the real-time status of all AI agents, key performance metrics, and quick-access tiles for each department.'),
    spacer(100),
    img('dashboard.png', { w: BODY_W, h: Math.round(BODY_W * 9/16) }),
    caption('Figure 3.1 — Main Dashboard showing 7/7 agents online and live metrics'),
    spacer(100),

    h2('Navigation Sidebar'),
    body('The left sidebar is always visible on authenticated pages. It contains:'),
    bullet('Dashboard — return to the overview at any time'),
    bullet('Chat Console — open a text conversation with any agent'),
    bullet('Voice Console — start a real-time voice session'),
    bullet('Department shortcuts — Reception, Customer Care, Sales, HR, Finance, Technology, Marketing'),
    bullet('Status bar — shows "ALL SYSTEMS NOMINAL" or active alerts'),
    bullet('Collapse button — hide the sidebar for more screen space'),
    spacer(100),
    img('10_sidebar_username.png', { w: Math.round(BODY_W * 0.6), h: Math.round(BODY_W * 0.6 * 9/16) }),
    caption('Figure 3.2 — Sidebar with username and all department links'),
    spacer(100),

    h2('Metrics Row'),
    body('Four live-updating tiles appear at the top of the Dashboard:'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.25), Math.round(BODY_W * 0.75)],
      rows: [
        ...([
          ['AGENTS ONLINE',   'Number of active agents / total (e.g. 7 / 7)'],
          ['ACTIVE SESSIONS', 'Conversations currently in progress'],
          ['AVG RESPONSE',    'Average time for agents to reply (SLA target: < 3s)'],
          ['WORKFLOWS RUN',   'Total automated workflows completed this session'],
        ].map(([m, d]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: m, font: 'Arial', size: 20, bold: true, color: AMBER })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.75), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: d, font: 'Arial', size: 20, color: LIGHT })] })] }),
        ]})))
      ],
    }),
    pageBreak(),

    // ── 4. AI Departments ────────────────────────────────────────────────────
    h1('4. AI Departments'),
    body('The platform provides seven fully autonomous AI departments. Each department agent has its own personality, memory, tool access, and escalation policy.'),
    spacer(100),

    h2('Department Overview Table'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [600, 1200, 3440, 2160, 1680],
      rows: [
        new TableRow({ tableHeader: true, children: [
          ...[['', 80], ['Dept', 100], ['Description', 100], ['Key Chat Tools', 100], ['Voice', 100]].map(([t, pad]) =>
            new TableCell({ borders: allBorders, shading: { fill: AMBER, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: pad, right: pad }, width: { size: [600,1200,3440,2160,1680][['', 'Dept','Description','Key Chat Tools','Voice'].indexOf(t)] || 600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: t, font: 'Arial', size: 20, bold: true, color: '000000' })] })] })
          ),
        ]}),
        deptRow('⭐', 'Receptionist', 'F59E0B', 'First contact, routing & visitor management', 'Greet, Route, FAQ, Escalate', 'Full TTS/STT'),
        deptRow('🎧', 'Customer Care', '22D3EE', 'Support tickets, issue resolution, follow-ups', 'Tickets, Resolve, Refunds, SLA', 'Full TTS/STT'),
        deptRow('🛒', 'Sales',         '4ADE80', 'Lead qualification, pipeline management, closing', 'Leads, CRM, Pipeline, Quotes', 'Full TTS/STT'),
        deptRow('👥', 'HR',            'C084FC', 'Recruitment, onboarding & HR policy', 'Recruit, Onboard, Policy, PTO', 'Full TTS/STT'),
        deptRow('💵', 'Finance',       'FB7185', 'Budgets, invoicing, reporting & audit trails', 'Invoices, Reports, Budget, Audit', 'Full TTS/STT'),
        deptRow('🖥️', 'Technology',    '38BDF8', 'IT support, infrastructure & DevOps automation', 'IT Help, DevOps, Infra, Security', 'Full TTS/STT'),
        deptRow('📣', 'Marketing',     'FB923C', 'Campaigns, analytics & content strategy', 'Campaigns, Analytics, Content', 'Full TTS/STT'),
      ],
    }),
    spacer(200),

    h2('How Department Routing Works'),
    body('You do not need to choose a department manually. Simply describe your request to any agent or from the Chat Console. The Director AI automatically:'),
    step(1, 'Analyzes the intent of your message'),
    step(2, 'Selects the most relevant department agent'),
    step(3, 'Routes your request — with full context — to that agent'),
    step(4, 'Receives the response and returns it to you within 2 seconds'),
    step(5, 'Logs the interaction in the session memory'),
    spacer(100),
    tip('You can also click directly on a department tile on the Dashboard to open a chat session pre-configured for that specific agent.'),
    pageBreak(),

    // ── 5. Chat Console ──────────────────────────────────────────────────────
    h1('5. Chat Console'),
    body('The Chat Console is the primary text interface. Type your question or request and press Enter or the send button. The Director AI routes your message to the best agent automatically.'),
    spacer(100),
    img('chat_console.png', { w: BODY_W, h: Math.round(BODY_W * 9/16) }),
    caption('Figure 5.1 — Chat Console with department selector and message thread'),
    spacer(100),

    h2('Starting a Chat Session'),
    step(1, 'Click "Chat Console" in the left sidebar, or click "New Chat" on the Dashboard'),
    step(2, 'Select a department from the dropdown (or leave on "Auto" for AI routing)'),
    step(3, 'Type your message in the input box at the bottom'),
    step(4, 'Press Enter or click the amber send button'),
    step(5, 'The agent\'s response appears in the message thread with a typing indicator'),
    spacer(100),

    h2('Chat Features'),
    bullet('Markdown rendering — responses support bold, lists, code blocks, and tables'),
    bullet('Conversation history — previous messages persist for the session'),
    bullet('Department switching — change the active department mid-conversation'),
    bullet('Agent handoff — agents can transfer to a specialist automatically'),
    bullet('File upload — attach documents (configure storage in .env)'),
    spacer(100),

    h2('Example Conversations by Department'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.3), Math.round(BODY_W * 0.7)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Say this...', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.7), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'The platform does this...', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['"I need to onboard a new employee"',        'HR Agent guides you through the onboarding checklist, generates documents, and schedules orientation'],
          ['"Our website is down"',                      'Technology Agent opens a P1 incident, escalates to on-call, and provides a resolution timeline'],
          ['"Show me Q3 revenue vs Q2"',                 'Finance Agent generates a comparison report and offers to export it to PDF or CSV'],
          ['"I\'d like to speak to someone in Sales"',   'Receptionist routes you to Sales Agent, which opens a qualified lead conversation in the CRM'],
          ['"Create a social media campaign for launch"', 'Marketing Agent drafts copy, suggests a posting schedule, and queues it for approval'],
        ].map(([q, a]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: q, font: 'Arial', size: 19, color: AMBER, italics: true })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.7), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: a, font: 'Arial', size: 19, color: LIGHT })] })] }),
        ]}))),
      ],
    }),
    pageBreak(),

    // ── 6. Voice Console ────────────────────────────────────────────────────
    h1('6. Voice Console'),
    body('The Voice Console enables real-time voice conversations with any department agent. You speak naturally; the platform converts your speech to text, processes it, and responds with a synthesized voice.'),
    spacer(100),
    img('voice_console.png', { w: BODY_W, h: Math.round(BODY_W * 9/16) }),
    caption('Figure 6.1 — Voice Console with microphone button and live transcript'),
    spacer(100),

    h2('Voice Session — Step by Step'),
    step(1, 'Click "Voice Console" in the sidebar or "Voice Call" on the Dashboard'),
    step(2, 'Select the target department from the department selector'),
    step(3, 'Click "Allow" when the browser requests microphone permission (first time only)'),
    step(4, 'Press the large amber microphone button (or push-to-talk)'),
    step(5, 'Speak your request clearly — the transcription appears in real time'),
    step(6, 'Release the button — the agent processes and speaks the response'),
    step(7, 'The live transcript is saved to your session history'),
    spacer(100),

    h2('Voice AI Stack'),
    body('The Voice Console uses a pluggable provider architecture. Your administrator configures the providers in the server .env file.'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.3), Math.round(BODY_W * 0.3), Math.round(BODY_W * 0.4)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Function', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Default Provider', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.4), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Alternatives Supported', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['Speech-to-Text (STT)', 'Deepgram',   'OpenAI Whisper, Azure Speech, Google STT'],
          ['Text-to-Speech (TTS)', 'ElevenLabs', 'OpenAI TTS, Azure TTS, Google TTS'],
          ['Realtime Streaming',   'WebSockets', 'LiveKit, WebRTC, Twilio Voice'],
          ['Language',             'English',    '30+ languages via provider settings'],
        ].map(([f, d, a]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: f, font: 'Arial', size: 19, color: AMBER })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: d, font: 'Arial', size: 19, color: LIGHT })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.4), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: a, font: 'Arial', size: 19, color: MUTED })] })] }),
        ]}))),
      ],
    }),
    spacer(100),
    noteBox('Microphone access is required for the Voice Console. The browser will prompt you once. If you accidentally clicked "Block", go to browser Settings → Privacy → Microphone and allow the platform URL.'),
    pageBreak(),

    // ── 7. Security & Accounts ───────────────────────────────────────────────
    h1('7. Security & User Accounts'),
    h2('Authentication'),
    body('All access is protected by JWT (JSON Web Token) authentication. Tokens are stored in the browser session and expire automatically.'),
    bullet('Default admin credentials: admin / admin — change immediately in production'),
    bullet('Tokens expire after the configured TTL (default: 24 hours)'),
    bullet('Logging out clears the token from all storage'),
    spacer(100),
    img('08_after_logout.png', { w: Math.round(BODY_W * 0.6), h: Math.round(BODY_W * 0.6 * 9/16) }),
    caption('Figure 7.1 — Redirect to /welcome after logout'),
    spacer(100),
    h2('Logging Out'),
    step(1, 'Click the user menu at the bottom of the sidebar'),
    step(2, 'Select "Sign Out"'),
    step(3, 'You will be redirected to the Welcome page; all session data is cleared'),
    spacer(100),
    tip('For shared workstations, always log out after each session. The platform does not auto-expire browser sessions unless the JWT TTL is reached.'),
    spacer(100),

    h2('Role-Based Access Control (RBAC)'),
    body('The platform supports multiple user roles. Contact your administrator to assign the appropriate role to your account.'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.25), Math.round(BODY_W * 0.75)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Role', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.75), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Permissions', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['admin',    'Full access to all departments, settings, analytics, and user management'],
          ['manager',  'Access to assigned departments, analytics dashboard, workflow monitoring'],
          ['operator', 'Chat & Voice Console, conversation history for assigned departments'],
          ['viewer',   'Read-only access to dashboards and analytics'],
        ].map(([r, p]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: r, font: 'Arial', size: 20, bold: true, color: AMBER, fontFamily: 'Courier New' })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.75), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: p, font: 'Arial', size: 20, color: LIGHT })] })] }),
        ]}))),
      ],
    }),
    pageBreak(),

    // ── 8. Troubleshooting ──────────────────────────────────────────────────
    h1('8. Troubleshooting'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.35), Math.round(BODY_W * 0.65)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.35), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Issue', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.65), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Solution', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['Page shows only "Loading…"',              'Check that the API server is running on port 8080 (docker compose ps)'],
          ['Login fails with "Invalid credentials"',  'Verify username/password. Default is admin/admin. Reset in users table if needed.'],
          ['Chat shows "Connection refused"',         'The API container may be unhealthy. Run: docker compose restart api'],
          ['Voice button does nothing',               'Grant microphone permission in browser settings. HTTPS is required in production for audio capture.'],
          ['Agent response is very slow (>10s)',      'Check OPENAI_API_KEY in .env. Free-tier keys have rate limits; upgrade plan or add a retry delay.'],
          ['API Online badge shows red/offline',      'The frontend cannot reach /api/v1/health. Check NEXT_PUBLIC_API_URL in frontend/.env.local.'],
          ['TTS produces no audio',                   'Check ELEVENLABS_API_KEY in .env. Test via curl: curl http://localhost:8080/api/v1/voice/speak'],
          ['STT returns 502 error',                   'Check DEEPGRAM_API_KEY in .env. Without a valid key, STT falls back to a mock response.'],
        ].map(([issue, sol]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.35), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: issue, font: 'Arial', size: 19, color: 'FCA5A5', bold: true })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.65), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: sol, font: 'Arial', size: 19, color: LIGHT })] })] }),
        ]}))),
      ],
    }),
    spacer(200),

    h2('Useful API Endpoints for Admins'),
    body('All backend endpoints are available at http://<host>:8080/api/v1/'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.35), Math.round(BODY_W * 0.15), Math.round(BODY_W * 0.5)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.35), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Endpoint', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.15), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Method', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Purpose', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['/health',            'GET',  'Platform health check (no auth required)'],
          ['/auth/token',        'POST', 'Exchange username/password for JWT token'],
          ['/chat/message',      'POST', 'Send a chat message to an agent'],
          ['/chat/sessions',     'GET',  'List active and recent chat sessions'],
          ['/voice/speak',       'POST', 'Convert text to audio (ElevenLabs TTS)'],
          ['/voice/transcribe',  'POST', 'Transcribe audio file to text (Deepgram STT)'],
          ['/voice/sessions',    'GET',  'List active voice sessions'],
          ['/mcp/crm/list',      'GET',  'List CRM contacts and pipeline (demo)'],
          ['/agents/status',     'GET',  'Current status of all 7 department agents'],
        ].map(([ep, m, p]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.35), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: ep, font: 'Courier New', size: 18, color: '93C5FD' })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.15), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: m, font: 'Arial', size: 18, color: m === 'GET' ? '4ADE80' : AMBER, bold: true })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: p, font: 'Arial', size: 18, color: LIGHT })] })] }),
        ]}))),
      ],
    }),
    pageBreak(),

    // ── 9. Quick Reference ───────────────────────────────────────────────────
    h1('9. Quick Reference Card'),
    h2('Default URLs'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.4), Math.round(BODY_W * 0.6)],
      rows: [
        ...([
          ['Welcome / Landing page',  'http://localhost:4000/welcome'],
          ['Login',                   'http://localhost:4000/login'],
          ['Dashboard',               'http://localhost:4000/'],
          ['Chat Console',            'http://localhost:4000/chat'],
          ['Voice Console',           'http://localhost:4000/voice'],
          ['API Base URL',            'http://localhost:8080/api/v1'],
          ['API Docs (Swagger)',       'http://localhost:8080/docs'],
          ['API Redoc',               'http://localhost:8080/redoc'],
        ].map(([label, url]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 70, bottom: 70, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.4), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: label, font: 'Arial', size: 20, color: LIGHT })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 70, bottom: 70, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.6), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: url, font: 'Courier New', size: 20, color: '93C5FD' })] })] }),
        ]}))),
      ],
    }),
    spacer(200),

    h2('Demo Credentials'),
    new Table({
      width: { size: Math.round(BODY_W * 0.5), type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.25), Math.round(BODY_W * 0.25)],
      rows: [
        ...([['Username', 'admin'], ['Password', 'admin']].map(([k, v]) =>
          new TableRow({ children: [
            new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: k, font: 'Arial', size: 20, bold: true, color: AMBER })] })] }),
            new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: v, font: 'Courier New', size: 20, color: LIGHT })] })] }),
          ]})
        )),
      ],
    }),
    spacer(200),

    noteBox('Change default credentials immediately for any production or shared-team deployment. Edit ADMIN_PASSWORD and ADMIN_USERNAME in your .env file, then restart the API container.'),
    pageBreak(),

    // ── 10. Platform Architecture ─────────────────────────────────────────
    h1('10. Platform Architecture (Overview)'),
    body('The AI Workforce Platform is a cloud-native, microservices architecture designed for horizontal scaling and high availability.'),
    spacer(100),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.33), Math.round(BODY_W * 0.33), Math.round(BODY_W * 0.34)],
      rows: [
        new TableRow({ children: [
          ...[
            ['Frontend Layer', ['Next.js 14 (React)', 'Tailwind CSS', 'Lucide Icons', 'Playwright E2E tests']],
            ['API Layer',      ['FastAPI (Python)', 'JWT Auth', 'WebSockets', 'OpenAPI / Swagger']],
            ['AI Layer',       ['Swarms Framework', 'OpenAI GPT-4o', 'HierarchicalSwarm', 'SwarmRouter']],
          ].map(([title, items]) =>
            new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 120, bottom: 120, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.33), type: WidthType.DXA }, children: [
              new Paragraph({ spacing: { before: 0, after: 80 }, children: [new TextRun({ text: title, font: 'Arial', size: 22, bold: true, color: AMBER })] }),
              ...items.map(i => new Paragraph({ spacing: { before: 30, after: 30 }, children: [new TextRun({ text: `• ${i}`, font: 'Arial', size: 19, color: LIGHT })] })),
            ]}),
          ),
        ]}),
        new TableRow({ children: [
          ...[
            ['Voice Layer',   ['ElevenLabs TTS', 'Deepgram STT', 'WebSocket Streaming', 'Pluggable providers']],
            ['Data Layer',    ['Redis (sessions)', 'ChromaDB (vector)', 'SQLite / Postgres', 'Conversation memory']],
            ['Integration',  ['Built-in CRM MCP', 'MCP Protocol (JSON-RPC 2.0)', 'HRIS / ERP adapters', 'Extensible tool registry']],
          ].map(([title, items]) =>
            new TableCell({ borders: allBorders, shading: { fill: DARK_BG, type: ShadingType.CLEAR }, margins: { top: 120, bottom: 120, left: 160, right: 160 }, width: { size: Math.round(BODY_W * 0.33), type: WidthType.DXA }, children: [
              new Paragraph({ spacing: { before: 0, after: 80 }, children: [new TextRun({ text: title, font: 'Arial', size: 22, bold: true, color: AMBER })] }),
              ...items.map(i => new Paragraph({ spacing: { before: 30, after: 30 }, children: [new TextRun({ text: `• ${i}`, font: 'Arial', size: 19, color: LIGHT })] })),
            ]}),
          ),
        ]}),
      ],
    }),
    spacer(200),
    h2('Deployment'),
    bullet('Docker Compose (local dev / single server): docker compose up --build'),
    bullet('Kubernetes: manifests in /k8s directory'),
    bullet('Supported clouds: AWS, Azure, GCP'),
    bullet('Environment variables: copy .env.example to .env and fill in API keys'),
    spacer(100),
    tip('Run docker compose ps to verify all containers are running. The API container logs are the first place to look if agents are not responding.'),
    pageBreak(),

    // ── Appendix ─────────────────────────────────────────────────────────────
    h1('Appendix: Required API Keys'),
    body('The following API keys must be configured in the .env file for full functionality. The platform runs in demo mode without them, but agent intelligence and voice features are limited.'),
    new Table({
      width: { size: BODY_W, type: WidthType.DXA },
      columnWidths: [Math.round(BODY_W * 0.3), Math.round(BODY_W * 0.25), Math.round(BODY_W * 0.45)],
      rows: [
        new TableRow({ tableHeader: true, children: [
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Variable', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Provider', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: '334155', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.45), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Required For', font: 'Arial', size: 20, bold: true, color: WHITE })] })] }),
        ]}),
        ...([
          ['OPENAI_API_KEY',       'OpenAI',      'All AI agent intelligence (required)'],
          ['ELEVENLABS_API_KEY',   'ElevenLabs',  'Text-to-Speech voice responses'],
          ['DEEPGRAM_API_KEY',     'Deepgram',    'Speech-to-Text transcription'],
          ['JWT_SECRET_KEY',       '—',           'Signing/verifying JWT tokens (required)'],
          ['REDIS_URL',            'Redis',       'Session state and memory (optional)'],
          ['DATABASE_URL',         'Postgres',    'Persistent conversation history (optional)'],
          ['LIVEKIT_API_KEY',      'LiveKit',     'WebRTC real-time voice streaming (optional)'],
          ['TWILIO_ACCOUNT_SID',   'Twilio',      'Phone call / SIP voice channel (optional)'],
        ].map(([v, p, r]) => new TableRow({ children: [
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.3), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: v, font: 'Courier New', size: 18, color: '93C5FD' })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.25), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: p, font: 'Arial', size: 18, color: AMBER })] })] }),
          new TableCell({ borders: allBorders, shading: { fill: MID_BG, type: ShadingType.CLEAR }, margins: { top: 60, bottom: 60, left: 120, right: 120 }, width: { size: Math.round(BODY_W * 0.45), type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: r, font: 'Arial', size: 18, color: LIGHT })] })] }),
        ]}))),
      ],
    }),
    spacer(300),
    new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '— End of Manual —', font: 'Arial', size: 22, color: MUTED, italics: true })] }),
  ],
};

// ─── build ────────────────────────────────────────────────────────────────────
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Arial', size: 22, color: LIGHT } },
      heading1: { run: { font: 'Arial', size: 36, bold: true, color: AMBER }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      heading2: { run: { font: 'Arial', size: 28, bold: true, color: WHITE }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      heading3: { run: { font: 'Arial', size: 24, bold: true, color: LIGHT }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    },
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } }, run: { color: AMBER } } }],
      },
      {
        reference: 'steps',
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } }, run: { color: AMBER, bold: true } } }],
      },
    ],
  },
  sections: [COVER_SECTION, MAIN_SECTION],
  background: { color: DARK_BG },
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log('✅ Manual written to', OUT);
}).catch(err => {
  console.error('❌ Error:', err.message);
  process.exit(1);
});
