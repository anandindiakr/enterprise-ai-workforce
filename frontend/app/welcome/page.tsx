"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  Zap, MessageSquare, Mic, Brain, Globe, Shield, Cpu,
  Star, HeadphonesIcon, ShoppingCart, Users, DollarSign,
  Megaphone, ArrowRight, CheckCircle2, ChevronDown, Play,
  BarChart3, Clock, Layers, Workflow,
} from "lucide-react";

// ─── tiny cn helper ────────────────────────────────────────────────────────
function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(" ");
}

// ─── data ───────────────────────────────────────────────────────────────────
const DEPARTMENTS = [
  { icon: Star,            label: "Receptionist",   color: "text-amber-400",  bg: "bg-amber-400/10",  desc: "First contact, routing & visitor management"      },
  { icon: HeadphonesIcon,  label: "Customer Care",  color: "text-cyan-400",   bg: "bg-cyan-400/10",   desc: "Support tickets, issue resolution & follow-ups"   },
  { icon: ShoppingCart,    label: "Sales",          color: "text-green-400",  bg: "bg-green-400/10",  desc: "Lead qualification, pipeline & closing"           },
  { icon: Users,           label: "HR",             color: "text-purple-400", bg: "bg-purple-400/10", desc: "Recruitment, onboarding & HR policy"              },
  { icon: DollarSign,      label: "Finance",        color: "text-rose-400",   bg: "bg-rose-400/10",   desc: "Budgets, invoicing, reporting & audit trails"     },
  { icon: Cpu,             label: "Technology",     color: "text-sky-400",    bg: "bg-sky-400/10",    desc: "IT support, infrastructure & DevOps automation"   },
  { icon: Megaphone,       label: "Marketing",      color: "text-orange-400", bg: "bg-orange-400/10", desc: "Campaigns, analytics & content strategy"          },
];

const FEATURES = [
  { icon: MessageSquare, title: "Real-Time Chat", desc: "Chat with any departmental agent instantly. Multi-session support, markdown rendering, and full conversation history." },
  { icon: Mic,           title: "Voice AI",        desc: "Speak naturally to agents. Speech-to-text, TTS responses, live transcripts, and multi-language support out of the box." },
  { icon: Brain,         title: "Multi-Agent Orchestration", desc: "A Director AI routes tasks to the right department automatically. Agents collaborate, escalate, and hand off seamlessly." },
  { icon: Workflow,      title: "MCP Tool Integrations", desc: "Agents connect to CRM, HRIS, ERP, ticketing, calendars, and more through modular MCP integrations." },
  { icon: Shield,        title: "Enterprise Security", desc: "JWT authentication, RBAC, encrypted secrets, tenant isolation, and full audit trails baked in from day one." },
  { icon: BarChart3,     title: "Analytics & Telemetry", desc: "Real-time dashboards, agent performance metrics, conversation analytics, and structured JSON logs." },
];

const BENEFITS = [
  "Cut first-response time from hours to seconds",
  "Run 7 specialized AI departments 24/7 with zero fatigue",
  "Eliminate repetitive tasks — escalate only what matters",
  "Onboard new departments without hiring overhead",
  "Unified voice + chat interface your team already knows",
  "Deploy on AWS, Azure, GCP, or your own datacenter",
];

const WHO_ITS_FOR = [
  {
    title: "Enterprise Organizations",
    emoji: "🏢",
    items: ["Replace tier-1 support queues", "Automate HR intake & onboarding", "Finance reporting on demand", "24/7 IT helpdesk coverage"],
  },
  {
    title: "Growing Startups & SMBs",
    emoji: "🚀",
    items: ["Operate like a 50-person team on day one", "Instant customer care without headcount", "Sales pipeline managed automatically", "Pay-as-you-scale cloud deployment"],
  },
  {
    title: "Service Businesses",
    emoji: "🎯",
    items: ["Reception & appointment routing", "Multi-language client support", "Follow-up & CRM sync automation", "Voice calls handled by AI agents"],
  },
];

// ─── animated counter ──────────────────────────────────────────────────────
function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    let start = 0;
    const step = target / 60;
    const id = setInterval(() => {
      start += step;
      if (start >= target) { setCount(target); clearInterval(id); } else { setCount(Math.floor(start)); }
    }, 16);
    return () => clearInterval(id);
  }, [target]);
  return <span ref={ref}>{count}{suffix}</span>;
}

// ─── main component ─────────────────────────────────────────────────────────
export default function WelcomePage() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 overflow-x-hidden">
      {/* ── Navbar ────────────────────────────────────── */}
      <header className={cn(
        "fixed top-0 inset-x-0 z-50 transition-all duration-300",
        scrolled ? "bg-[#030712]/90 backdrop-blur border-b border-white/5 shadow-xl" : ""
      )}>
        <div className="mx-auto max-w-7xl flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500 shadow-lg shadow-amber-500/30">
              <Zap className="h-4 w-4 text-black" />
            </div>
            <span className="text-base font-bold tracking-widest" style={{ fontFamily: "var(--font-syne)" }}>
              WORKFORCE
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#features" className="hover:text-slate-100 transition-colors">Features</a>
            <a href="#departments" className="hover:text-slate-100 transition-colors">Departments</a>
            <a href="#who" className="hover:text-slate-100 transition-colors">Who It&apos;s For</a>
            <a href="#benefits" className="hover:text-slate-100 transition-colors">Benefits</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-slate-400 hover:text-slate-100 transition-colors px-3 py-1.5">
              Sign in
            </Link>
            <Link href="/login" className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-semibold text-black hover:bg-amber-400 transition-colors shadow-lg shadow-amber-500/20">
              Get Started <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ──────────────────────────────────────── */}
      <section className="relative pt-32 pb-24 px-6 text-center overflow-hidden">
        {/* glow */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-[600px] w-[600px] rounded-full bg-amber-500/5 blur-[120px]" />
        </div>
        <div className="pointer-events-none absolute top-0 left-1/4 h-[400px] w-[400px] rounded-full bg-cyan-500/5 blur-[100px]" />

        <div className="relative mx-auto max-w-4xl">
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/10 px-4 py-1.5 text-xs text-amber-400 font-mono tracking-widest uppercase">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
            Enterprise AI Workforce Platform — 7 Departments Online
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight leading-none mb-6" style={{ fontFamily: "var(--font-syne)" }}>
            Your Entire Company,<br />
            <span className="text-amber-400">Powered by AI</span>
          </h1>

          <p className="mx-auto max-w-2xl text-lg text-slate-400 leading-relaxed mb-10">
            Deploy a full-stack AI workforce in minutes. Seven specialized departments — Receptionist, Sales, HR, Finance, Technology, Customer Care, and Marketing — available via chat or voice, 24&nbsp;/&nbsp;7.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/login" className="flex items-center gap-2 rounded-xl bg-amber-500 px-8 py-3.5 text-base font-bold text-black hover:bg-amber-400 transition-all shadow-2xl shadow-amber-500/25 hover:scale-[1.02]">
              Launch Platform <ArrowRight className="h-4 w-4" />
            </Link>
            <a href="#features" className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-8 py-3.5 text-base font-medium text-slate-300 hover:bg-white/10 transition-all">
              <Play className="h-4 w-4" /> See How It Works
            </a>
          </div>
        </div>

        {/* stats row */}
        <div className="relative mx-auto mt-16 max-w-3xl grid grid-cols-2 md:grid-cols-4 gap-px rounded-2xl overflow-hidden border border-white/5 bg-white/5">
          {[
            { label: "AI Agents", value: 7,    suffix: "" },
            { label: "Response SLA", value: 2, suffix: "s" },
            { label: "Channels", value: 2,     suffix: "" },
            { label: "Uptime",    value: 99,   suffix: "%" },
          ].map((s) => (
            <div key={s.label} className="bg-[#0c111d] px-6 py-5 text-center">
              <div className="text-3xl font-bold text-amber-400 font-mono">
                <Counter target={s.value} suffix={s.suffix} />
              </div>
              <div className="mt-1 text-xs text-slate-500 uppercase tracking-widest">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="mt-10 flex justify-center">
          <a href="#features" className="text-slate-600 hover:text-slate-400 transition-colors animate-bounce">
            <ChevronDown className="h-6 w-6" />
          </a>
        </div>
      </section>

      {/* ── Features ──────────────────────────────────── */}
      <section id="features" className="py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <p className="text-xs font-mono uppercase tracking-widest text-amber-400 mb-3">Platform Capabilities</p>
            <h2 className="text-4xl font-bold" style={{ fontFamily: "var(--font-syne)" }}>
              Everything You Need.<br /><span className="text-slate-400">Nothing You Don&apos;t.</span>
            </h2>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div key={f.title} className="group rounded-2xl border border-white/5 bg-[#0c111d] p-6 hover:border-amber-500/20 hover:bg-[#0f1622] transition-all">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 group-hover:bg-amber-500/15 transition-colors">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="mb-2 font-semibold text-slate-100">{f.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ──────────────────────────────── */}
      <section className="py-20 px-6 bg-[#060b14]">
        <div className="mx-auto max-w-5xl">
          <div className="text-center mb-14">
            <p className="text-xs font-mono uppercase tracking-widest text-cyan-400 mb-3">Workflow</p>
            <h2 className="text-3xl font-bold" style={{ fontFamily: "var(--font-syne)" }}>How It Works</h2>
          </div>
          <div className="relative grid md:grid-cols-4 gap-6">
            {[
              { step: "01", icon: Globe,    title: "Connect",  desc: "Open the web app or make a voice call — no installs needed" },
              { step: "02", icon: Brain,    title: "Route",    desc: "The Director AI identifies intent and selects the right agent" },
              { step: "03", icon: Layers,   title: "Execute",  desc: "The agent uses MCP tools — CRM, calendar, ticketing — to act" },
              { step: "04", icon: Clock,    title: "Deliver",  desc: "Response arrives in under 2 seconds via chat or spoken audio" },
            ].map((item, i) => (
              <div key={item.step} className="relative text-center">
                {i < 3 && (
                  <div className="hidden md:block absolute top-6 left-[calc(50%+28px)] w-[calc(100%-56px)] h-px bg-gradient-to-r from-amber-500/30 to-transparent" />
                )}
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400">
                  <item.icon className="h-5 w-5" />
                </div>
                <div className="text-[10px] font-mono text-amber-500 mb-1">{item.step}</div>
                <h4 className="font-semibold mb-1">{item.title}</h4>
                <p className="text-xs text-slate-500 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Departments ───────────────────────────────── */}
      <section id="departments" className="py-24 px-6">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <p className="text-xs font-mono uppercase tracking-widest text-purple-400 mb-3">AI Departments</p>
            <h2 className="text-4xl font-bold" style={{ fontFamily: "var(--font-syne)" }}>
              Seven Departments.<br /><span className="text-slate-400">All Online. Always.</span>
            </h2>
            <p className="mt-4 text-slate-500 max-w-xl mx-auto">Each agent has its own personality, tools, memory, and escalation policy — just like a real department head.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {DEPARTMENTS.map((d) => (
              <div key={d.label} className="group rounded-2xl border border-white/5 bg-[#0c111d] p-5 hover:border-white/10 transition-all hover:-translate-y-0.5">
                <div className={cn("mb-3 flex h-9 w-9 items-center justify-center rounded-xl", d.bg)}>
                  <d.icon className={cn("h-4 w-4", d.color)} />
                </div>
                <div className="flex items-center justify-between mb-1">
                  <h3 className="font-semibold text-sm">{d.label}</h3>
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">{d.desc}</p>
                <div className="mt-3 flex gap-1.5">
                  <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-500 font-mono">Chat</span>
                  <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-500 font-mono">Voice</span>
                </div>
              </div>
            ))}
            {/* +1 slot = future extensibility card */}
            <div className="rounded-2xl border border-dashed border-white/10 bg-transparent p-5 flex flex-col items-center justify-center text-center gap-2 hover:border-white/20 transition-all cursor-pointer">
              <div className="h-9 w-9 rounded-xl border border-dashed border-white/15 flex items-center justify-center text-slate-600 text-lg">+</div>
              <p className="text-xs text-slate-600 font-mono">Add your own<br />department</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Who it's for ──────────────────────────────── */}
      <section id="who" className="py-24 px-6 bg-[#060b14]">
        <div className="mx-auto max-w-6xl">
          <div className="text-center mb-16">
            <p className="text-xs font-mono uppercase tracking-widest text-green-400 mb-3">Built For Everyone</p>
            <h2 className="text-4xl font-bold" style={{ fontFamily: "var(--font-syne)" }}>Who It&apos;s For</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {WHO_ITS_FOR.map((w) => (
              <div key={w.title} className="rounded-2xl border border-white/5 bg-[#0c111d] p-6">
                <div className="text-3xl mb-3">{w.emoji}</div>
                <h3 className="font-bold text-lg mb-4" style={{ fontFamily: "var(--font-syne)" }}>{w.title}</h3>
                <ul className="space-y-2.5">
                  {w.items.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-sm text-slate-400">
                      <CheckCircle2 className="h-4 w-4 text-green-400 mt-0.5 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Benefits ──────────────────────────────────── */}
      <section id="benefits" className="py-24 px-6">
        <div className="mx-auto max-w-6xl">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <div>
              <p className="text-xs font-mono uppercase tracking-widest text-amber-400 mb-3">Why Teams Love It</p>
              <h2 className="text-4xl font-bold mb-6 leading-tight" style={{ fontFamily: "var(--font-syne)" }}>
                Real Business Impact,<br />Starting Day One
              </h2>
              <p className="text-slate-500 leading-relaxed mb-8">
                The AI Workforce Platform isn&apos;t a chatbot. It&apos;s a complete autonomous workforce — every department thinks, acts, and communicates on behalf of your organization.
              </p>
              <Link href="/login" className="inline-flex items-center gap-2 rounded-xl bg-amber-500 px-6 py-3 text-sm font-bold text-black hover:bg-amber-400 transition-all shadow-xl shadow-amber-500/20">
                Start Free Demo <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
            <div className="grid grid-cols-1 gap-3">
              {BENEFITS.map((b) => (
                <div key={b} className="flex items-center gap-3 rounded-xl border border-white/5 bg-[#0c111d] px-4 py-3">
                  <CheckCircle2 className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span className="text-sm text-slate-300">{b}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Tech stack strip ──────────────────────────── */}
      <section className="py-12 px-6 border-y border-white/5 bg-[#060b14]">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-xs font-mono uppercase tracking-widest text-slate-600 mb-6">Built on production-grade infrastructure</p>
          <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-slate-600 font-mono">
            {["FastAPI", "Next.js 14", "Swarms Framework", "OpenAI", "ElevenLabs TTS", "Deepgram STT", "Redis", "ChromaDB", "Docker", "Kubernetes"].map((t) => (
              <span key={t} className="rounded-lg border border-white/5 px-3 py-1.5 bg-white/2 hover:text-slate-400 transition-colors">{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────── */}
      <section className="relative py-28 px-6 text-center overflow-hidden">
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="h-[500px] w-[500px] rounded-full bg-amber-500/8 blur-[120px]" />
        </div>
        <div className="relative mx-auto max-w-2xl">
          <h2 className="text-5xl font-extrabold mb-6 leading-tight" style={{ fontFamily: "var(--font-syne)" }}>
            Ready to Deploy<br /><span className="text-amber-400">Your AI Workforce?</span>
          </h2>
          <p className="text-slate-400 mb-10 text-lg">
            Sign in with the demo credentials and explore all 7 departments, live chat, voice AI, and MCP integrations — right now.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/login" className="flex items-center gap-2 rounded-xl bg-amber-500 px-10 py-4 text-base font-bold text-black hover:bg-amber-400 transition-all shadow-2xl shadow-amber-500/25 hover:scale-[1.02]">
              Launch Platform <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <p className="mt-5 text-xs text-slate-600 font-mono">Demo: admin / admin &nbsp;·&nbsp; No signup required</p>
        </div>
      </section>

      {/* ── Footer ────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-8 px-6">
        <div className="mx-auto max-w-7xl flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-500">
              <Zap className="h-3.5 w-3.5 text-black" />
            </div>
            <span className="text-sm font-bold tracking-widest text-slate-400" style={{ fontFamily: "var(--font-syne)" }}>WORKFORCE</span>
          </div>
          <p className="text-xs text-slate-600">Enterprise AI Workforce Platform — All departments active 24/7</p>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <Link href="/login" className="hover:text-slate-400 transition-colors">Sign In</Link>
            <span>·</span>
            <a href="#features" className="hover:text-slate-400 transition-colors">Features</a>
            <span>·</span>
            <a href="#departments" className="hover:text-slate-400 transition-colors">Departments</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
