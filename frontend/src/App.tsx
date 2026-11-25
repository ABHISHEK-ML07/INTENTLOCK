import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BadgeCheck,
  Ban, BookOpen, Check, CheckCircle2, ChevronDown, ChevronRight,
  CircleAlert, Clock3, Command, Compass, ExternalLink, FileCheck2,
  Fingerprint, Globe2, Layers3, LockKeyhole, Menu, Play, Plus,
  RefreshCw, Shield, ShieldAlert, ShieldCheck, Sparkles, Terminal,
  Wallet, X, Zap,
} from "lucide-react";

type Contract = {
  contract_id: string;
  task_id: string;
  version: number;
  goal: string;
  constraints: {
    max_total_price?: { amount: string | number; currency: string; basis: string } | null;
    max_distance_km?: string | number | null;
    refundable_required: boolean;
    allowed_domains: string[];
    prohibited_actions: string[];
  };
  status: "proposed" | "confirmed";
  assumptions: string[];
  clarification_required: string[];
  created_at: string;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  contract_hash?: string | null;
};

type Offer = {
  hotel_id: string;
  hotel_name: string;
  room_id: string;
  marketing_cancellation_claim: string;
  detailed_cancellation_policy: string;
  base_price_inr: string;
  final_total_inr: string;
  distance_km: string;
  marketing_policy_conflict: boolean;
  suspicious_page_instruction_detected: boolean;
  simulated_booking_blocked: boolean;
  instruction_handling: string;
  decision: "allow" | "deny" | "pause";
  eligible: boolean;
  reasons: string[];
  evidence_sources: string[];
  navigation_checks_passed: number;
};

type DemoReport = {
  contract_id: string;
  contract_version: number;
  demo_mode: string;
  offers: Offer[];
  eligible_count: number;
  rejected_or_paused_count: number;
  completed_at: string;
  disclaimer: string;
};

type LogEvent = {
  id: number;
  time: string;
  title: string;
  detail: string;
  kind: "success" | "warning" | "danger" | "neutral";
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const DEFAULT_TASK = "Find a refundable hotel within 5 km for under ₹5,000 total. Compare options, but do not book or pay.";

function money(value?: string | number | null) {
  if (value === undefined || value === null || value === "") return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(numeric)
    : String(value);
}

function clock(value = new Date()) {
  return value.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    const message = typeof detail === "string"
      ? detail
      : detail?.message || JSON.stringify(detail || data) || response.statusText;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [activeView, setActiveView] = useState<"overview" | "evidence" | "activity">("overview");
  const [task, setTask] = useState(DEFAULT_TASK);
  const [domains, setDomains] = useState("localhost");
  const [contract, setContract] = useState<Contract | null>(null);
  const [report, setReport] = useState<DemoReport | null>(null);
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [backend, setBackend] = useState<"checking" | "online" | "offline">("checking");
  const [busy, setBusy] = useState<"propose" | "confirm" | "run" | null>(null);
  const [error, setError] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);

  const addEvent = (title: string, detail: string, kind: LogEvent["kind"] = "neutral") => {
    setEvents((previous) => [{ id: Date.now() + Math.random(), time: clock(), title, detail, kind }, ...previous]);
  };

  const refreshHealth = async () => {
    try {
      await api("/health");
      setBackend("online");
    } catch {
      setBackend("offline");
    }
  };

  useEffect(() => {
    void refreshHealth();
    const interval = window.setInterval(() => void refreshHealth(), 12000);
    return () => window.clearInterval(interval);
  }, []);

  const canConfirm = Boolean(
    contract &&
    contract.status === "proposed" &&
    contract.clarification_required.length === 0 &&
    contract.constraints.allowed_domains.length > 0,
  );
  const readyToRun = contract?.status === "confirmed";
  const progress = report ? 4 : readyToRun ? 3 : contract ? 2 : 1;

  const counts = useMemo(() => ({
    allow: report?.offers.filter((offer) => offer.decision === "allow").length ?? 0,
    deny: report?.offers.filter((offer) => offer.decision === "deny").length ?? 0,
    pause: report?.offers.filter((offer) => offer.decision === "pause").length ?? 0,
  }), [report]);

  const proposeContract = async () => {
    setBusy("propose");
    setError("");
    setReport(null);
    setContract(null);
    try {
      const allowedDomains = domains.split(",").map((domain) => domain.trim()).filter(Boolean);
      const proposed = await api<Contract>("/contracts/propose", {
        method: "POST",
        body: JSON.stringify({ task, allowed_domains: allowedDomains }),
      });
      setContract(proposed);
      addEvent("Intent contract generated", `Extracted ${proposed.constraints.allowed_domains.length} allowed domain(s) and reviewed constraints.`, "success");
      if (proposed.clarification_required.length) {
        addEvent("Clarification required", proposed.clarification_required.join(" "), "warning");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the intent contract.");
      addEvent("Contract proposal failed", err instanceof Error ? err.message : "API request failed.", "danger");
    } finally {
      setBusy(null);
    }
  };

  const confirmContract = async () => {
    if (!contract) return;
    setBusy("confirm");
    setError("");
    try {
      const confirmed = await api<Contract>(`/contracts/${contract.contract_id}/confirm`, {
        method: "POST",
        body: JSON.stringify({ confirmed_by: "dashboard-user" }),
      });
      setContract(confirmed);
      addEvent("Contract confirmed", "The user-reviewed constraints are now the active policy for the local demo.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not confirm the contract.");
    } finally {
      setBusy(null);
    }
  };

  const runDemo = async () => {
    if (!contract) return;
    setBusy("run");
    setError("");
    setReport(null);
    try {
      const result = await api<DemoReport>("/browser/run-demo", {
        method: "POST",
        body: JSON.stringify({ contract_id: contract.contract_id }),
      });
      setReport(result);
      setActiveView("overview");
      addEvent("Browser comparison completed", `${result.eligible_count} offer(s) allowed; ${result.rejected_or_paused_count} rejected or paused.`, "success");
      result.offers.forEach((offer) => {
        addEvent(
          `${offer.hotel_name}: ${offer.decision.toUpperCase()}`,
          offer.reasons[0] || "Policy evaluation completed.",
          offer.decision === "allow" ? "success" : offer.decision === "deny" ? "danger" : "warning",
        );
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The browser demonstration failed.");
      addEvent("Browser run failed", err instanceof Error ? err.message : "API request failed.", "danger");
    } finally {
      setBusy(null);
    }
  };

  const reset = () => {
    setContract(null);
    setReport(null);
    setError("");
    setTask(DEFAULT_TASK);
    setDomains("localhost");
    setActiveView("overview");
    addEvent("Workspace reset", "Ready for a new intent contract.", "neutral");
  };

  const nav = [
    { id: "overview" as const, label: "Mission control", icon: Layers3 },
    { id: "evidence" as const, label: "Evidence ledger", icon: FileCheck2 },
    { id: "activity" as const, label: "Activity log", icon: Activity },
  ];

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Shield size={19} strokeWidth={2.4} /></div>
          <div>
            <div className="brand-name">INTENTLOCK<span>™</span></div>
            <div className="brand-sub">CONSTRAINT INTEGRITY ENGINE</div>
          </div>
          <button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18}/></button>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <div className="workspace-card">
          <div className="workspace-icon"><Command size={17}/></div>
          <div className="workspace-copy"><strong>Autonomous web</strong><span>Local sandbox / Demo 01</span></div>
          <ChevronDown size={14} className="muted-icon"/>
        </div>

        <div className="nav-label">PLATFORM</div>
        <nav className="side-nav">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={`nav-item ${activeView === item.id ? "active" : ""}`} onClick={() => { setActiveView(item.id); setMobileNav(false); }}>
                <Icon size={17}/><span>{item.label}</span>
                {item.id === "evidence" && report && <span className="nav-count">{report.offers.length}</span>}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-spacer"/>
        <div className="security-card">
          <div className="security-orbit"><LockKeyhole size={17}/></div>
          <div className="security-title">Safety boundary active</div>
          <p>Every demo navigation is checked against the confirmed contract.</p>
          <div className="security-foot"><span className="live-dot"/>{backend === "online" ? "POLICY API CONNECTED" : backend === "checking" ? "CHECKING API…" : "API DISCONNECTED"}</div>
        </div>
        <div className="sidebar-footer"><span>INTENTLOCK</span><span>v0.2.0 · LOCAL</span></div>
      </aside>

      {mobileNav && <button className="mobile-backdrop" onClick={() => setMobileNav(false)} aria-label="Close navigation"/>}

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={19}/></button>
            <div className="breadcrumb">Workspace <ChevronRight size={14}/> <strong>{nav.find((n) => n.id === activeView)?.label}</strong></div>
          </div>
          <div className="topbar-right">
            <div className={`connection-pill ${backend}`}><span className="live-dot"/>{backend === "online" ? "API CONNECTED" : backend === "checking" ? "CONNECTING" : "API OFFLINE"}</div>
            <div className="avatar">AN</div>
          </div>
        </header>

        <div className="page-content">
          <section className="hero-row">
            <div>
              <div className="eyebrow"><span className="eyebrow-line"/>AUTONOMOUS WEB · CONTROL PLANE</div>
              <h1>{activeView === "overview" ? <>Keep the web<br/><em>within your intent.</em></> : activeView === "evidence" ? <>Proof behind<br/><em>every decision.</em></> : <>Every action.<br/><em>Accounted for.</em></>}</h1>
              <p className="hero-description">
                {activeView === "overview"
                  ? "Translate a request into a policy the browser cannot silently rewrite. Review it, lock it, then watch INTENTLOCK enforce it."
                  : activeView === "evidence"
                    ? "Inspect the source-backed claims used to approve or reject each synthetic hotel offer."
                    : "A transparent execution timeline for contract creation, confirmation, evidence checks and policy decisions."}
              </p>
            </div>
            <div className="hero-status">
              <div className="status-kicker">SYSTEM STATUS</div>
              <div className="status-main"><span className={`status-light ${backend === "online" ? "good" : "bad"}`}/>{backend === "online" ? "Operational" : backend === "checking" ? "Connecting" : "Offline"}</div>
              <div className="status-detail"><span className="status-line"/> Local policy environment</div>
              <div className="hero-status-bottom"><span>BUILD</span><strong>0.2.0 / SANDBOX</strong></div>
            </div>
          </section>

          <section className="workflow-strip">
            {[
              { n: "01", title: "Define intent", detail: "Natural language" },
              { n: "02", title: "Review contract", detail: "User confirmation" },
              { n: "03", title: "Execute safely", detail: "Policy gateway" },
              { n: "04", title: "Verify outcome", detail: "Evidence + audit" },
            ].map((step, index) => (
              <div key={step.n} className={`workflow-step ${progress > index ? "complete" : ""} ${progress === index + 1 ? "current" : ""}`}>
                <div className="workflow-number">{progress > index + 1 ? <Check size={13}/> : step.n}</div>
                <div><strong>{step.title}</strong><span>{step.detail}</span></div>
                {index < 3 && <div className="workflow-connector"/>}
              </div>
            ))}
          </section>

          {error && <div className="error-banner"><CircleAlert size={18}/><div><strong>Something needs attention</strong><span>{error}</span></div><button onClick={() => setError("")} aria-label="Dismiss"><X size={16}/></button></div>}

          {activeView === "overview" && (
            <>
              <section className="section-heading">
                <div><span className="section-index">01 / INTENT COMPILER</span><h2>Define the mission</h2></div>
                <div className="section-aside"><span className="mini-dot"/> PROPOSAL MODE</div>
              </section>

              <div className="content-grid">
                <section className="panel request-panel">
                  <div className="panel-heading">
                    <div className="panel-icon violet"><Sparkles size={18}/></div>
                    <div><h3>What should the agent do?</h3><p>Describe the task in plain language. INTENTLOCK extracts the constraints.</p></div>
                    <span className="panel-tag">INPUT</span>
                  </div>
                  <label className="field-label" htmlFor="task">YOUR INSTRUCTION</label>
                  <textarea id="task" value={task} onChange={(e) => setTask(e.target.value)} rows={4} placeholder="Describe your task, limits and actions the agent must not take…"/>
                  <div className="prompt-hint"><Sparkles size={13}/> Be explicit about price basis, distance, and actions that are off-limits.</div>
                  <button className="advanced-toggle" onClick={() => setShowAdvanced(!showAdvanced)}>
                    <Globe2 size={15}/> Website permissions <span className="advanced-value">{domains || "No domains selected"}</span><ChevronDown size={15} className={showAdvanced ? "rotate" : ""}/>
                  </button>
                  {showAdvanced && (
                    <div className="advanced-box">
                      <label className="field-label" htmlFor="domains">ALLOWED DOMAINS <span>Comma-separated hostnames</span></label>
                      <input id="domains" value={domains} onChange={(e) => setDomains(e.target.value)} placeholder="localhost"/>
                      <div className="field-note"><LockKeyhole size={13}/> The demo is restricted to localhost. Do not add external domains.</div>
                    </div>
                  )}
                  <div className="panel-actions">
                    <button className="button button-ghost" onClick={reset}><RefreshCw size={15}/> Reset</button>
                    <button className="button button-primary" onClick={proposeContract} disabled={busy !== null || backend !== "online" || !task.trim() || !domains.trim()}>
                      {busy === "propose" ? <span className="spinner"/> : <Zap size={16}/>} {busy === "propose" ? "Compiling…" : "Compile intent"} <ArrowRight size={16}/>
                    </button>
                  </div>
                </section>

                <section className="panel principle-panel">
                  <div className="principle-top"><div className="panel-icon green"><ShieldCheck size={19}/></div><span className="panel-tag">CORE PRINCIPLE</span></div>
                  <h3>LLMs interpret.<br/><em>Policy decides.</em></h3>
                  <p>Web content is data, never authority. The confirmed contract stays in control of the browser.</p>
                  <div className="principle-rule"/>
                  <div className="principle-points">
                    <div><span className="point-icon"><Fingerprint size={15}/></span><span><strong>Intent integrity</strong><small>Constraints stay fixed</small></span><CheckCircle2 size={15} className="point-check"/></div>
                    <div><span className="point-icon"><FileCheck2 size={15}/></span><span><strong>Evidence integrity</strong><small>Claims carry provenance</small></span><CheckCircle2 size={15} className="point-check"/></div>
                    <div><span className="point-icon"><Ban size={15}/></span><span><strong>Action integrity</strong><small>Policy gates execution</small></span><CheckCircle2 size={15} className="point-check"/></div>
                  </div>
                </section>
              </div>

              {contract && (
                <>
                  <section className="section-heading contract-heading">
                    <div><span className="section-index">02 / USER-REVIEWABLE POLICY</span><h2>Intent contract</h2></div>
                    <span className={`state-badge ${contract.status}`}><span/> {contract.status === "confirmed" ? "CONFIRMED & LOCKED" : "AWAITING CONFIRMATION"}</span>
                  </section>
                  <section className="panel contract-panel">
                    <div className="contract-topline">
                      <div className="contract-id"><span>CONTRACT ID</span><code>{contract.contract_id.slice(0, 8).toUpperCase()}…</code><span className="contract-version">V{contract.version}</span></div>
                      {contract.contract_hash && <div className="hash-chip"><Fingerprint size={13}/> SHA-256 SEALED</div>}
                    </div>
                    <div className="contract-goal">“{contract.goal}”</div>
                    <div className="constraint-grid">
                      <Constraint icon={<Wallet size={17}/>} label="TOTAL PRICE LIMIT" value={contract.constraints.max_total_price ? money(contract.constraints.max_total_price.amount) : "Not specified"} detail={contract.constraints.max_total_price?.basis ? contract.constraints.max_total_price.basis.replace("_", " ").toUpperCase() : "PRICE BASIS"} />
                      <Constraint icon={<Compass size={17}/>} label="MAXIMUM DISTANCE" value={contract.constraints.max_distance_km ? `${contract.constraints.max_distance_km} km` : "Not specified"} detail="FROM DEMO VENUE" />
                      <Constraint icon={<BadgeCheck size={17}/>} label="CANCELLATION" value={contract.constraints.refundable_required ? "Refundable only" : "No restriction"} detail="SELECTED ROOM POLICY" />
                      <Constraint icon={<Globe2 size={17}/>} label="ALLOWED SITES" value={contract.constraints.allowed_domains.join(", ") || "None"} detail="DOMAIN ALLOW-LIST" />
                    </div>
                    <div className="contract-bottom">
                      <div className="prohibited-list"><span className="field-label">PROHIBITED ACTIONS</span><div>{contract.constraints.prohibited_actions.map((action) => <span key={action} className="prohibited-chip"><Ban size={12}/>{action.replaceAll("_", " ")}</span>)}</div></div>
                      {contract.status === "proposed" ? (
                        <button className="button button-confirm" disabled={!canConfirm || busy !== null} onClick={confirmContract}>
                          {busy === "confirm" ? <span className="spinner"/> : <LockKeyhole size={15}/>} {busy === "confirm" ? "Confirming…" : "I confirm this contract"} <ArrowRight size={15}/>
                        </button>
                      ) : (
                        <div className="confirmed-meta"><ShieldCheck size={17}/><span><strong>Policy locked</strong><small>Confirmed by {contract.confirmed_by || "user"}</small></span></div>
                      )}
                    </div>
                    {contract.clarification_required.length > 0 && (
                      <div className="clarification-box"><CircleAlert size={17}/><div><strong>Clarification required before confirmation</strong>{contract.clarification_required.map((item) => <span key={item}>• {item}</span>)}</div></div>
                    )}
                    {contract.assumptions.length > 0 && <div className="assumption-note"><CircleAlert size={14}/>{contract.assumptions.join(" ")}</div>}
                    {contract.status === "confirmed" && (
                      <div className="run-bar">
                        <div><div className="run-bar-title"><span className="live-dot"/> POLICY GATEWAY READY</div><p>Run three local hotel scenarios. No external sites, bookings or payments.</p></div>
                        <button className="button button-run" onClick={runDemo} disabled={busy !== null}>
                          {busy === "run" ? <span className="spinner"/> : <Play size={16} fill="currentColor"/>} {busy === "run" ? "Running browser…" : "Run protected browser"} <ArrowUpRight size={16}/>
                        </button>
                      </div>
                    )}
                  </section>
                </>
              )}

              {report && (
                <>
                  <section className="section-heading results-heading">
                    <div><span className="section-index">03 / EXECUTION RESULT</span><h2>Policy decisions</h2></div>
                    <div className="run-time"><Clock3 size={14}/> {new Date(report.completed_at).toLocaleString("en-IN")}</div>
                  </section>
                  <div className="metric-grid">
                    <Metric label="OFFERS EVALUATED" value={report.offers.length} icon={<Layers3 size={17}/>} tone="neutral"/>
                    <Metric label="POLICY ALLOWED" value={counts.allow} icon={<ShieldCheck size={17}/>} tone="good"/>
                    <Metric label="DENIED" value={counts.deny} icon={<Ban size={17}/>} tone="bad"/>
                    <Metric label="PAUSED" value={counts.pause} icon={<Clock3 size={17}/>} tone="warn"/>
                  </div>
                  <div className="offer-list">
                    {report.offers.map((offer) => <OfferCard key={offer.hotel_id} offer={offer}/>)}
                  </div>
                  <div className="demo-disclaimer"><Shield size={14}/>{report.disclaimer}</div>
                </>
              )}
            </>
          )}

          {activeView === "evidence" && (
            <EvidenceView report={report} onReturn={() => setActiveView("overview")}/>
          )}

          {activeView === "activity" && (
            <ActivityView events={events} onClear={() => setEvents([])}/>
          )}

          <footer className="page-footer">
            <div><span className="footer-mark"><Shield size={13}/></span><strong>INTENTLOCK</strong><span>THE CONSTRAINT INTEGRITY ENGINE</span></div>
            <p>LLMs interpret. Deterministic code validates and decides. The controlled browser executes.</p>
          </footer>
        </div>
      </main>
    </div>
  );
}

function Constraint({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return <div className="constraint-tile"><div className="constraint-head">{icon}<span>{label}</span></div><strong>{value}</strong><small>{detail}</small></div>;
}

function Metric({ label, value, icon, tone }: { label: string; value: number; icon: React.ReactNode; tone: string }) {
  return <div className={`metric-card ${tone}`}><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong></div></div>;
}

function OfferCard({ offer }: { offer: Offer }) {
  const [expanded, setExpanded] = useState(false);
  const statusClass = offer.decision === "allow" ? "allow" : offer.decision === "deny" ? "deny" : "pause";
  return (
    <article className="offer-card">
      <div className="offer-main">
        <div className="offer-avatar">{offer.hotel_name.split(" ").slice(0,2).map((word) => word[0]).join("")}</div>
        <div className="offer-info">
          <div className="offer-title-line"><h3>{offer.hotel_name}</h3><span className={`decision-badge ${statusClass}`}>{offer.decision === "allow" ? <CheckCircle2 size={13}/> : offer.decision === "deny" ? <Ban size={13}/> : <Clock3 size={13}/>} {offer.decision.toUpperCase()}</span></div>
          <p>{offer.room_id} <span>·</span> {offer.distance_km} km from demo venue</p>
          <div className="offer-flags">
            {offer.marketing_policy_conflict && <span className="flag flag-warn"><CircleAlert size={12}/> Marketing / policy conflict</span>}
            {offer.suspicious_page_instruction_detected && <span className="flag flag-danger"><ShieldAlert size={12}/> Injection attempt detected</span>}
            {offer.simulated_booking_blocked && <span className="flag flag-good"><Ban size={12}/> Booking proposal blocked</span>}
          </div>
        </div>
        <div className="offer-price"><span>FINAL TOTAL</span><strong>{money(offer.final_total_inr)}</strong><small>Advertised {money(offer.base_price_inr)}</small></div>
      </div>
      <div className="offer-reason"><span className={`reason-symbol ${statusClass}`}>{offer.decision === "allow" ? <Check size={14}/> : <ShieldAlert size={14}/>}</span><span>{offer.reasons[0] || "Policy evaluation complete."}</span><button onClick={() => setExpanded(!expanded)}>{expanded ? "Hide details" : "Inspect evidence"} <ChevronDown size={14} className={expanded ? "rotate" : ""}/></button></div>
      {expanded && (
        <div className="offer-expanded">
          <div className="expanded-column"><span className="field-label">SELECTED ROOM CANCELLATION POLICY</span><p>{offer.detailed_cancellation_policy}</p><small>Marketing claim: {offer.marketing_cancellation_claim}</small></div>
          <div className="expanded-column"><span className="field-label">POLICY REASONS</span>{offer.reasons.map((reason) => <p key={reason} className="reason-line"><ArrowDownRight size={13}/>{reason}</p>)}</div>
          <div className="expanded-column full"><span className="field-label">EVIDENCE SOURCES · {offer.navigation_checks_passed} NAVIGATION CHECKS PASSED</span>{offer.evidence_sources.map((source) => <a key={source} href={source} target="_blank" rel="noreferrer"><ExternalLink size={12}/>{source.replace("http://localhost:8000", "localhost:8000")}</a>)}</div>
          {offer.instruction_handling && <div className="instruction-note"><ShieldCheck size={14}/>{offer.instruction_handling}</div>}
        </div>
      )}
    </article>
  );
}

function EvidenceView({ report, onReturn }: { report: DemoReport | null; onReturn: () => void }) {
  if (!report) return <div className="empty-state"><div className="empty-icon"><FileCheck2 size={25}/></div><h3>No evidence captured yet</h3><p>Run the protected browser comparison to populate the evidence ledger with offer policies, checkout totals and source locations.</p><button className="button button-primary" onClick={onReturn}>Go to mission control <ArrowRight size={15}/></button></div>;
  return (
    <section className="evidence-page">
      <div className="ledger-summary"><div><span>CAPTURED OFFERS</span><strong>{report.offers.length}</strong></div><div><span>VERIFIED SOURCE PAGES</span><strong>{report.offers.reduce((total, item) => total + item.evidence_sources.length, 0)}</strong></div><div><span>POLICY CONFLICTS</span><strong>{report.offers.filter((item) => item.marketing_policy_conflict).length}</strong></div></div>
      {report.offers.map((offer) => (
        <article className="panel evidence-card" key={offer.hotel_id}>
          <div className="evidence-card-head"><div><span className="section-index">OFFER / {offer.hotel_id.toUpperCase()}</span><h3>{offer.hotel_name}</h3></div><span className={`decision-badge ${offer.decision}`}>{offer.decision.toUpperCase()}</span></div>
          <div className="evidence-table">
            <EvidenceRow claim="Final checkout total" value={money(offer.final_total_inr)} source={offer.evidence_sources[2]} result={Number(offer.final_total_inr) <= 5000 ? "Within demo cap" : "Over demo cap"} good={Number(offer.final_total_inr) <= 5000}/>
            <EvidenceRow claim="Selected room refundability" value={offer.detailed_cancellation_policy} source={offer.evidence_sources[1]} result={offer.marketing_policy_conflict ? "Conflicts with marketing" : "Policy captured"} good={!offer.marketing_policy_conflict}/>
            <EvidenceRow claim="Distance" value={`${offer.distance_km} km`} source={offer.evidence_sources[0]} result="Captured from demo page" good/>
          </div>
          {offer.suspicious_page_instruction_detected && <div className="security-event"><ShieldAlert size={16}/><div><strong>Untrusted page instruction detected</strong><span>{offer.instruction_handling}</span></div></div>}
          {offer.simulated_booking_blocked && <div className="security-event safe"><Ban size={16}/><div><strong>Unauthorised action blocked</strong><span>Simulated booking proposal was denied before browser dispatch.</span></div></div>}
        </article>
      ))}
      <div className="ledger-footnote"><LockKeyhole size={14}/> Evidence currently comes from INTENTLOCK's own synthetic local pages. Third-party website verification is not yet implemented.</div>
    </section>
  );
}

function EvidenceRow({ claim, value, source, result, good }: { claim: string; value: string; source?: string; result: string; good: boolean }) {
  return <div className="evidence-row"><div><span className="field-label">{claim}</span><strong>{value}</strong>{source && <a href={source} target="_blank" rel="noreferrer"><ExternalLink size={11}/> Source page</a>}</div><span className={`evidence-result ${good ? "good" : "bad"}`}>{good ? <CheckCircle2 size={12}/> : <CircleAlert size={12}/>} {result}</span></div>;
}

function ActivityView({ events, onClear }: { events: LogEvent[]; onClear: () => void }) {
  return (
    <section className="panel activity-panel">
      <div className="activity-head"><div><span className="section-index">AUDIT TRAIL / SESSION</span><h2>Execution timeline</h2><p>Chronological record of the actions taken in this dashboard session.</p></div><button className="button button-ghost" onClick={onClear} disabled={!events.length}>Clear log</button></div>
      {!events.length ? <div className="empty-activity"><Clock3 size={22}/><strong>No activity recorded</strong><span>Compile an intent contract to begin the audit trail.</span></div> : (
        <div className="timeline">
          {events.map((event) => <div className="timeline-item" key={event.id}><div className={`timeline-marker ${event.kind}`}>{event.kind === "success" ? <Check size={13}/> : event.kind === "danger" ? <Ban size={13}/> : event.kind === "warning" ? <CircleAlert size={13}/> : <Activity size={13}/>}</div><div className="timeline-copy"><div><strong>{event.title}</strong><time>{event.time}</time></div><p>{event.detail}</p></div></div>)}
        </div>
      )}
      <div className="audit-note"><ShieldCheck size={15}/> This is a browser-session UI log. It is not yet a tamper-resistant server-side audit log.</div>
    </section>
  );
}

export default App;
