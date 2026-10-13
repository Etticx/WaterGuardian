"use client";
import { useEffect, useState, useCallback } from "react";
import { Droplets, LayoutDashboard, Waves, ClipboardList, GitBranch, Settings2, Factory, Trees, Store, ArrowUpRight, ArrowRight, ChevronRight, ChevronDown, Play, Pause, RotateCcw, Activity as ActivityIcon, Radio, ShieldCheck, CircleHelp, Search, Bell, Check, X, Loader2, Cpu, Database, Plug, FileChartColumn, CheckCircle2, AlertTriangle } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { request, type Overview, type Asset, type Order, type Recording, type Settings, type Evaluation, type Incident } from "@/lib/api";

type Tab = "overview" | "incidents" | "orders" | "activity" | "evaluation" | "settings";
const nav = [
  { id: "overview" as Tab, label: "Overview", icon: LayoutDashboard },
  { id: "incidents" as Tab, label: "Investigations", icon: Waves },
  { id: "orders" as Tab, label: "Work orders", icon: ClipboardList },
  { id: "activity" as Tab, label: "Agent activity", icon: GitBranch },
  { id: "evaluation" as Tab, label: "Evaluation", icon: FileChartColumn },
];
const zoneIcons = { industrial: Factory, parks: Trees, malls: Store };
const titles = { overview: "Water operations", incidents: "Investigations", orders: "Work orders", activity: "Agent activity", evaluation: "Model evaluation", settings: "System settings" };
const statusLabels: Record<string, string> = { model_pending: "Awaiting model", normal: "Normal", leak: "Suspected leakage", sensor_fault: "Sensor issue", review: "Needs review", investigating: "Investigating", pending_approval: "Awaiting approval", approved: "Approved", in_progress: "In progress", completed: "Completed", rejected: "Rejected", error: "Needs attention" };
const label = (s: string) => statusLabels[s] || s;
const stamp = (s: string) => new Date(s).toLocaleTimeString("en-MY", { hour: "2-digit", minute: "2-digit" });
const fmt = (n?: number) => n === undefined ? "—" : n.toLocaleString("en-MY", { maximumFractionDigits: 3 });

function Badge({ status, children }: { status?: string; children?: React.ReactNode }) {
  return <span className={`badge badge-${status || "neutral"}`}><span className="status-dot" />{children || label(status || "")}</span>;
}

function Empty({ icon: Icon, title, children }: { icon: typeof Waves; title: string; children: React.ReactNode }) {
  return <div className="empty"><div className="empty-icon"><Icon size={23} /></div><h3>{title}</h3><p>{children}</p></div>;
}

function ZoneCard({ asset, active, onClick }: { asset: Asset; active: boolean; onClick: () => void }) {
  const Icon = zoneIcons[asset.zone as keyof typeof zoneIcons] || Factory;
  const last = asset.latest?.values;
  return <button className={`zone-card ${active ? "zone-active" : ""}`} onClick={onClick} aria-pressed={active}>
    <div className="zone-top"><span className={`zone-icon zone-${asset.zone}`}><Icon size={20} /></span><span className="zone-code">{asset.id.replace("zone-", "BLOCK 0")}</span><ArrowUpRight size={16} className="zone-arrow" /></div>
    <h3>{asset.name}</h3><div className="zone-status"><Badge status={asset.status} /></div>
    <div className="zone-bottom"><div><span className="small-label">Flow channel 1</span><strong>{fmt(last?.["Water Flow 1"])}</strong><small>sensor units</small></div>
      <div className="spark"><ResponsiveContainer width="100%" height={58}><AreaChart data={asset.history.slice(-45)}><defs><linearGradient id={`spark-${asset.id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7195ad" stopOpacity={0.18} /><stop offset="100%" stopColor="#7195ad" stopOpacity={0} /></linearGradient></defs><Area type="monotone" dataKey="Water Flow 1" stroke="#7195ad" strokeWidth={1.6} fill={`url(#spark-${asset.id})`} isAnimationActive={false} /></AreaChart></ResponsiveContainer></div></div>
    <div className="zone-foot"><Radio size={12} />Virtual device<span>{fmt(asset.readings_count)} readings</span></div>
  </button>;
}

function SignalChart({ asset, channel, setChannel }: { asset: Asset; channel: string; setChannel: (v: string) => void }) {
  const pressure = channel.startsWith("Pressure");
  return <section className="panel chart-panel"><div className="panel-heading"><div><h2>Sensor readings</h2><p>{asset.name} <span className="divider-dot">·</span> {asset.recording_id.replace("run-", "Recording ")}</p></div>
    <select aria-label="Sensor channel" className="select" value={channel} onChange={e => setChannel(e.target.value)}>{["Water Flow 1", "Water Flow 2", "Water Flow 3", "Water Flow 4", "Pressure 1 Out", "Pressure 2 Out", "Pressure 3 In", "Pressure 4 In"].map(c => <option key={c}>{c}</option>)}</select></div>
    <div className="chart-legend"><span className={pressure ? "legend-dot sand" : "legend-dot"} />{channel}<span className="chart-unit">Original sensor units</span></div>
    <div className="main-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={asset.history} margin={{ top: 15, right: 10, left: 0, bottom: 12 }}>
      <defs><linearGradient id="signal-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={pressure ? "#b59a7c" : "#6b93ae"} stopOpacity={0.19} /><stop offset="100%" stopColor="#ffffff" stopOpacity={0.04} /></linearGradient></defs>
      <CartesianGrid vertical={false} stroke="#eceeea" strokeDasharray="3 3" /><XAxis dataKey="sample_index" axisLine={false} tickLine={false} minTickGap={45} tick={{ fontSize: 11, fill: "#8a969f" }} label={{ value: "Recorded sample index", position: "insideBottom", offset: -10, fill: "#8a969f", fontSize: 11 }} />
      <YAxis axisLine={false} tickLine={false} width={52} domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "#8a969f" }} tickFormatter={n => Number(n).toFixed(2)} />
      <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e3e8e9", fontSize: 12 }} labelFormatter={n => `Recorded sample ${n}`} formatter={v => [Number(v).toFixed(4), channel]} />
      <Area type="monotone" dataKey={channel} stroke={pressure ? "#b59a7c" : "#648eab"} strokeWidth={2} fill="url(#signal-fill)" isAnimationActive={false} />
    </AreaChart></ResponsiveContainer></div>
    <div className="chart-footer"><span><Database size={12} />WDSEventDB recorded measurements</span><span>Playback speed does not represent the original sampling interval.</span></div>
  </section>;
}

export default function Dashboard() {
  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<Overview | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [assetId, setAssetId] = useState("zone-1");
  const [channel, setChannel] = useState("Water Flow 1");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [toast, setToast] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const [speed, setSpeed] = useState("0.5");
  const [source, setSource] = useState("");
  const [sample, setSample] = useState("120");
  const [incidentId, setIncidentId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { const d = await request<Overview>("/api/overview"); setData(d); setError(""); }
    catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { refresh(); const timer = setInterval(refresh, 2000); return () => clearInterval(timer); }, [refresh]);
  const hasData = Boolean(data);
  useEffect(() => { if (hasData) request<Recording[]>("/api/recordings").then(setRecordings).catch(() => {}); }, [hasData]);
  useEffect(() => { if (tab === "settings") Promise.all([request<Settings>("/api/settings"), request<Recording[]>("/api/recordings")]).then(([s, r]) => { setSettings(s); setRecordings(r); }).catch(e => setError(e.message)); if (tab === "evaluation") request<Evaluation>("/api/evaluation").then(setEvaluation).catch(e => setError(e.message)); }, [tab]);
  useEffect(() => { if (toast) { const t = setTimeout(() => setToast(""), 5000); return () => clearTimeout(t); } }, [toast]);
  const asset = data?.assets.find(a => a.id === assetId) || data?.assets[0];
  useEffect(() => { if (asset) { setSource(asset.recording_id); setSample(String(asset.cursor)); } }, [assetId, asset?.recording_id]); // Preserve an edited offset during live refresh.
  const act = async (key: string, path: string, body?: object, method = "POST") => {
    setBusy(key);
    try { const r = await request(path, { method, body: body ? JSON.stringify(body) : undefined }); await refresh(); return r; }
    catch (e) { setToast((e as Error).message); return null; }
    finally { setBusy(""); }
  };
  const investigate = async () => {
    if (!asset) return;
    const result = await act("investigate", `/api/assets/${asset.id}/investigate`) as { incident: Incident; created: boolean } | null;
    if (result) { setIncidentId(result.incident.id); setTab("incidents"); setToast(result.created ? "Investigation started. Follow its progress in Agent activity." : "This zone already has an open investigation."); }
  };
  const decide = async (decision: "approve" | "reject") => {
    if (!order) return;
    const result = await act("decision", `/api/work-orders/${order.id}/decision`, { decision, note: decisionNote });
    if (result) { setOrder(null); setDecisionNote(""); setToast(decision === "approve" ? "Inspection task approved." : "Inspection task rejected."); }
  };
  const allOrders = (data?.work_orders || []).filter(w => (filter === "all" || w.status === filter) && `${w.id} ${w.title}`.toLowerCase().includes(search.toLowerCase()));
  const chosenIncident = data?.incidents.find(i => i.id === incidentId) || data?.incidents[0];
  const nameFor = (id: string) => data?.assets.find(a => a.id === id)?.name || id;
  const showOrder = (w: Order) => { setOrder(w); setDecisionNote(""); };

  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="/" aria-label="Water Guardian overview"><span className="brand-mark"><Droplets size={25} strokeWidth={1.7} /></span><span>Water Guardian<small>TOWNSHIP OPERATIONS</small></span></a>
      <div className="workspace"><span className="workspace-icon"><Factory size={16} /></span><div>Township workspace<small>Prototype environment</small></div><ChevronDown size={14} /></div>
      <span className="nav-label">WORKSPACE</span><nav>{nav.map(n => <button key={n.id} className={`nav-item ${tab === n.id ? "nav-active" : ""}`} onClick={() => { setTab(n.id); setFilter("all"); }}><n.icon size={18} strokeWidth={1.7} />{n.label}{n.id === "orders" && !!data?.stats.pending_approval && <span className="nav-count">{data.stats.pending_approval}</span>}</button>)}</nav>
      <div className="sidebar-spacer" /><div className="sidebar-note"><span className="sidebar-note-icon"><Radio size={17} /></span><strong>Real data. Recorded replay.</strong><p>Physical laboratory measurements, presented in illustrative township zones.</p><a href="https://github.com/Moazeni-s-Concise-Lab/WDSEventDB" target="_blank" rel="noreferrer">Explore the dataset <ArrowUpRight size={13} /></a></div>
      <button className={`nav-item settings-nav ${tab === "settings" ? "nav-active" : ""}`} onClick={() => setTab("settings")}><Settings2 size={18} />System settings</button>
      <div className="sidebar-profile"><span className="avatar">WG</span><div>Operations team<small><span className={`connection-dot ${data && !error ? "connected" : ""}`} />{data && !error ? "Backend connected" : "Connecting to backend"}</small></div></div>
    </aside>
    <main className="main"><header className="topbar"><div>Workspace <ChevronRight size={13} /><span>{titles[tab]}</span></div><div><span className="environment"><span />LOCAL PROTOTYPE</span><button className="icon-button" aria-label="Show pending approvals" onClick={() => { setTab("orders"); setFilter("pending_approval"); }}><Bell size={18} />{!!data?.stats.pending_approval && <i />}</button><span className="avatar small-avatar">WG</span></div></header>
      <div className="content"><div className="page-heading"><div><div className="eyebrow">TOWNSHIP WATER GUARDIAN</div><h1>{titles[tab]}</h1><p>{tab === "overview" ? "A clear view of your readings, investigations and next actions." : tab === "incidents" ? "Review observations and follow each investigation to a decision." : tab === "orders" ? "Review, authorise and track inspection tasks." : tab === "activity" ? "Follow the evidence through each step of the agent workflow." : tab === "evaluation" ? "Measured results from your separately trained Monitor." : "Manage providers, data replay and your Monitor integration."}</p></div>
        {tab === "overview" && <div className="heading-actions"><select className="select speed-select" aria-label="Replay speed" value={speed} onChange={e => setSpeed(e.target.value)}><option value="1">Slow replay</option><option value="0.5">Standard replay</option><option value="0.1">Fast replay</option></select><Button variant="outline" size="icon" aria-label="Reset replay" disabled={!!busy || !data} onClick={() => act("reset", "/api/replay/control/reset")}><RotateCcw size={16} /></Button><Button disabled={!!busy || !data} onClick={() => act("replay", `/api/replay/control/${data?.replay.running ? "pause" : "start"}?interval=${speed}`)}>{busy === "replay" ? <Loader2 size={15} className="spin" /> : data?.replay.running ? <Pause size={15} /> : <Play size={15} />}{data?.replay.running ? "Pause replay" : "Start replay"}</Button></div>}
      </div>
      {error && <div className="error-banner"><AlertTriangle size={18} /><div><strong>Backend connection needs attention</strong><span>{error}. Start the project services, then retry.</span></div><Button variant="outline" size="sm" onClick={refresh}>Retry</Button></div>}
      {!data ? <div className="loading-panel"><Loader2 className="spin" size={27} /><h2>Connecting to your workspace</h2><p>Loading the real recordings and operations state.</p></div> : <>
      {tab === "overview" && <>
        <div className="stats-grid">{[
          { title: "Monitored zones", value: data.stats.zones, icon: LayoutDashboard, sub: "Three illustrative asset groups" },
          { title: "Recorded readings", value: data.stats.readings, icon: ActivityIcon, sub: "Stored in current replay sessions" },
          { title: "Open investigations", value: data.stats.open_incidents, icon: Waves, sub: "Evidence awaiting a resolution" },
          { title: "Awaiting approval", value: data.stats.pending_approval, icon: ClipboardList, sub: "Inspection tasks for your review" },
        ].map(s => <section className="stat" key={s.title}><div><span>{s.title}</span><s.icon size={17} /></div><strong>{fmt(s.value)}</strong><small>{s.sub}</small></section>)}</div>
        {!data.monitor.connected && <div className="model-banner"><span className="model-icon"><Cpu size={20} /></span><div><strong>Your workspace is ready for the Monitor model</strong><p>Explore real readings and run manual investigations. ML predictions will begin when your trained model is connected.</p></div><button onClick={() => setTab("settings")}>Model setup <ArrowRight size={15} /></button></div>}
        <div className="section-heading"><div><h2>Township zones <span>03</span></h2><p>Select a zone to explore its sensor readings.</p></div><Badge status={data.replay.running ? "normal" : "neutral"}>{data.replay.running ? "Publishing recorded data" : "Replay paused"}</Badge></div>
        <div className="zones-grid">{data.assets.map(a => <ZoneCard key={a.id} asset={a} active={asset?.id === a.id} onClick={() => setAssetId(a.id)} />)}</div>
        <div className="detail-grid">{asset && <SignalChart asset={asset} channel={channel} setChannel={setChannel} />}
          <section className="panel insight-panel"><div className="panel-heading"><div><h2>Investigation workspace</h2><p>Evidence before action</p></div><span className="outline-icon"><ShieldCheck size={19} /></span></div>
            <div className="insight-illustration"><Waves size={30} strokeWidth={1.5} /><span className="illustration-line" /><GitBranch size={24} strokeWidth={1.5} /><span className="illustration-line" /><ClipboardList size={25} strokeWidth={1.5} /></div>
            <h3>{asset?.latest?.prediction ? label(asset.latest.prediction.classification) : "Ready for a closer look"}</h3><p>{asset?.latest?.prediction ? "The Monitor has assessed the current readings. Open an investigation to review the evidence and prepare an inspection task." : "The trained Monitor will assess each incoming sample. You can already ask the workflow to review the current sensor window."}</p>
            <div className="insight-facts"><div><span>Selected asset</span><strong>{asset?.name}</strong></div><div><span>Monitor</span><strong>{data.monitor.connected ? "Connected" : "Training separately"}</strong></div><div><span>Action authorisation</span><strong>Operator approval</strong></div></div>
            <Button className="w-full" onClick={investigate} disabled={!!busy || !asset?.history.length}>{busy === "investigate" ? <Loader2 size={15} className="spin" /> : <Search size={15} />}Investigate readings<ArrowRight size={15} /></Button>
          </section>
        </div>
        <div className="bottom-grid"><section className="panel"><div className="panel-heading"><div><h2>Recent investigations</h2><p>From sensor evidence to inspection</p></div><button className="text-link" onClick={() => setTab("incidents")}>View all <ArrowRight size={13} /></button></div>{data.incidents.length ? <div className="compact-list">{data.incidents.slice(0, 3).map(i => <button key={i.id} onClick={() => { setIncidentId(i.id); setTab("incidents"); }}><span className="list-icon"><Waves size={17} /></span><div><strong>{i.title}</strong><small>{i.id} · {stamp(i.created_at)}</small></div><Badge status={i.status} /></button>)}</div> : <Empty icon={Waves} title="No investigations opened">Start a manual review from a zone, or connect the Monitor to open investigations automatically.</Empty>}</section>
          <section className="panel"><div className="panel-heading"><div><h2>Workflow activity</h2><p>Latest system events</p></div><button className="text-link" onClick={() => setTab("activity")}>View all <ArrowRight size={13} /></button></div><div className="activity-preview">{data.activity.slice(0, 3).map(a => <div key={a.id}><span className="activity-dot" /><div><strong>{a.agent}</strong><p>{a.message}</p></div><time>{stamp(a.created_at)}</time></div>)}</div></section></div>
      </>}
      {tab === "incidents" && <div className="investigation-grid"><section className="panel"><div className="panel-heading"><h2>All investigations</h2><Badge>{data.incidents.length} total</Badge></div>{data.incidents.length ? <div className="incident-list">{data.incidents.map(i => <button className={chosenIncident?.id === i.id ? "selected" : ""} key={i.id} onClick={() => setIncidentId(i.id)}><div><strong>{nameFor(i.asset_id)}</strong><Badge status={i.status} /></div><span>{i.id}</span><small>{label(i.classification)} · {stamp(i.created_at)}</small></button>)}</div> : <Empty icon={Waves} title="Begin with the readings">Select a zone on Overview and choose Investigate readings.</Empty>}</section>
        <section className="panel incident-detail">{chosenIncident ? <><div className="panel-heading"><div><h2>{chosenIncident.title}</h2><p>{chosenIncident.id}</p></div><Badge status={chosenIncident.status} /></div><div className="incident-body"><div className="two-facts"><div><span>Assessment</span><strong>{label(chosenIncident.classification)}</strong></div><div><span>Priority</span><strong className="capitalize">{chosenIncident.priority}</strong></div></div>
          {chosenIncident.error && <p className="inline-error">{chosenIncident.error}</p>}
          {chosenIncident.diagnosis ? <><h3>Diagnosis</h3><p>{chosenIncident.diagnosis.summary}</p><span className="provider-label">{chosenIncident.diagnosis.provider === "evidence_only" ? "Evidence-only fallback · no LLM response" : `Generated with ${chosenIncident.diagnosis.provider}`}</span><h3>Recorded observations</h3><ul className="evidence-list">{chosenIncident.diagnosis.observations.map((e, i) => <li key={i}><CheckCircle2 size={15} />{e}</li>)}</ul><h3>Recommended inspection</h3><p>{chosenIncident.diagnosis.recommended_action}</p><Button onClick={() => { const w = data.work_orders.find(w => w.incident_id === chosenIncident.id); if (w) showOrder(w); else setTab("activity"); }}><ClipboardList size={15} />{data.work_orders.some(w => w.incident_id === chosenIncident.id) ? "Review inspection task" : "Follow agent activity"}</Button></> : chosenIncident.status === "error" ? <div className="progress-review"><AlertTriangle size={25} /><h3>This investigation needs attention</h3><p>Return to the zone to review its readings and open another investigation.</p><Button variant="outline" onClick={() => { setAssetId(chosenIncident.asset_id); setTab("overview"); }}>Review zone<ArrowRight size={14} /></Button></div> : <div className="progress-review"><Loader2 size={25} className="spin" /><h3>Agents are reviewing the evidence</h3><p>Diagnosis and task preparation run in the background. This view updates automatically.</p></div>}
        </div></> : <Empty icon={Search} title="Select an investigation">The evidence, recommendation and approval task will appear here.</Empty>}</section></div>}
      {tab === "orders" && <section className="panel"><div className="table-toolbar"><div className="search-field"><Search size={16} /><input aria-label="Search work orders" placeholder="Search work orders…" value={search} onChange={e => setSearch(e.target.value)} /></div><select aria-label="Work order status" className="select" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All statuses</option>{["pending_approval", "approved", "in_progress", "completed", "rejected"].map(s => <option value={s} key={s}>{label(s)}</option>)}</select></div>{allOrders.length ? <div className="table-scroll"><table><thead><tr><th>Task</th><th>Zone</th><th>Assigned crew</th><th>Status</th><th /></tr></thead><tbody>{allOrders.map(w => <tr key={w.id}><td><strong>{w.title}</strong><small>{w.id}</small></td><td>{nameFor(w.asset_id)}</td><td>{data.crews.find(c => c.id === w.crew_id)?.name || "Unassigned"}</td><td><Badge status={w.status} /></td><td><Button variant="outline" size="sm" onClick={() => showOrder(w)}>Review <ArrowUpRight size={13} /></Button></td></tr>)}</tbody></table></div> : <Empty icon={ClipboardList} title={search || filter !== "all" ? "No matching tasks" : "Inspection tasks appear after a review"}>Diagnosis and Dispatch prepare a draft. You approve it before work can begin.</Empty>}</section>}
      {tab === "activity" && <section className="panel"><div className="panel-heading"><div><h2>Agent execution log</h2><p>Persisted workflow events and provider attribution</p></div><Badge><Database size={12} />SQLite</Badge></div><div className="activity-timeline">{data.activity.map(a => <div key={a.id}><span className="timeline-icon">{a.agent === "Human approval" ? <ShieldCheck size={17} /> : a.agent === "Replay" ? <Radio size={17} /> : <GitBranch size={17} />}</span><div><div className="timeline-title"><strong>{a.agent}</strong>{a.provider && <span className="provider-label">{a.provider.replace("_", " ")}</span>}<time>{stamp(a.created_at)}</time></div><p>{a.message}</p>{a.incident_id && <button className="text-link" onClick={() => { setIncidentId(a.incident_id); setTab("incidents"); }}>{a.incident_id}<ArrowUpRight size={12} /></button>}</div></div>)}</div></section>}
      {tab === "evaluation" && <section className="panel evaluation-panel"><div className="panel-heading"><div><h2>Monitor performance</h2><p>Results are loaded from the separate training workflow.</p></div><Badge status={data.monitor.connected ? "normal" : "model_pending"}>{data.monitor.connected ? "Model connected" : "Training separately"}</Badge></div>{evaluation?.available ? <div className="evaluation-body"><div className="stats-grid">{[["Accuracy", `${((evaluation.accuracy || 0)*100).toFixed(1)}%`], ["Macro F1", evaluation.macro_f1?.toFixed(3)], ["Test samples", fmt(evaluation.samples)], ["Model version", evaluation.model_version]].map(([k, v]) => <div className="stat" key={k}><span>{k}</span><strong>{v}</strong></div>)}</div><h3>Evaluation split</h3><p>{evaluation.split_description}</p><h3>Confusion matrix</h3><p>Rows are actual classes. Columns are predicted classes.</p><div className="table-scroll"><table><thead><tr><th>Actual / predicted</th>{evaluation.class_names?.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{evaluation.confusion_matrix?.map((row, i) => <tr key={i}><th>{evaluation.class_names?.[i]}</th>{row.map((n, j) => <td key={j}>{n}</td>)}</tr>)}</tbody></table></div></div> : <div className="evaluation-pending"><span className="large-icon"><FileChartColumn size={35} strokeWidth={1.3} /></span><h2>Ready for your training results</h2><p>Train and evaluate the Monitor separately. Connect its model file and export your measured metrics to see the results here.</p><div className="evaluation-steps"><div><span>01</span><strong>Train independently</strong><p>Keep recordings separate between training and testing.</p></div><div><span>02</span><strong>Connect the model</strong><p>Load the exported joblib bundle through Model setup.</p></div><div><span>03</span><strong>Review measured results</strong><p>Publish actual metrics and the confusion matrix.</p></div></div><Button variant="outline" onClick={() => setTab("settings")}>Open model setup<ArrowRight size={14} /></Button></div>}</section>}
      {tab === "settings" && <div className="settings-grid"><section className="panel"><div className="panel-heading"><div><h2>Language model providers</h2><p>Groq → Gemini → local Qwen fallback</p></div><Plug size={19} /></div><div className="settings-body">{settings?.providers.map((p, i) => <div className="provider-row" key={p.name}><span className="provider-number">0{i+1}</span><div><strong>{p.name}</strong><small>{p.model}</small></div><Badge status={p.configured ? "normal" : "model_pending"}>{p.name === "Ollama" ? "Local endpoint" : p.configured ? "Key configured" : "Add API key"}</Badge></div>)}<p className="settings-note">Add your keys to the backend environment file and restart the API. Provider failures fall back automatically; the execution log identifies which provider answered.</p></div></section>
        <section className="panel"><div className="panel-heading"><div><h2>Monitor integration</h2><p>A separate ML model, connected when ready</p></div><Cpu size={19} /></div><div className="settings-body"><Badge status={data.monitor.connected ? "normal" : "model_pending"}>{data.monitor.connected ? "Connected" : "Model not connected"}</Badge><dl><dt>Model file</dt><dd>{data.monitor.path}</dd><dt>Version</dt><dd>{data.monitor.version || "Not loaded"}</dd><dt>Required bundle fields</dt><dd>model, features, class_map</dd></dl>{data.monitor.error && <p className="inline-error">{data.monitor.error}</p>}<Button disabled={!!busy} variant="outline" onClick={async () => { const r = await act("model", "/api/model/reload") as { connected: boolean } | null; if (r) setToast(r.connected ? "Monitor model connected." : "Monitor is not connected. Check the model file and export format."); }}><RotateCcw size={14} />Reload model</Button></div></section>
        <section className="panel"><div className="panel-heading"><div><h2>Device replay</h2><p>Publish recorded measurements over HTTP</p></div><Radio size={19} /></div><div className="settings-body"><label className="field-label">Zone<select className="select" value={assetId} onChange={e => setAssetId(e.target.value)}>{data.assets.map(a => <option value={a.id} key={a.id}>{a.name}</option>)}</select></label><label className="field-label">Recording<select className="select" value={source} onChange={e => setSource(e.target.value)}>{recordings.map(r => <option key={r.id} value={r.id}>{r.name} · {fmt(r.samples)} samples</option>)}</select></label><label className="field-label">Starting sample<input className="input" type="number" min="0" value={sample} onChange={e => setSample(e.target.value)} /></label><Button variant="outline" disabled={data.replay.running || !!busy || !source} onClick={async () => { const r = await act("configure", "/api/replay/configure", { asset_id: assetId, recording_id: source, start_sample: Number(sample) }); if (r) setToast("Recorded source assigned to the virtual device."); }}>Apply recording<ArrowRight size={14} /></Button>{data.replay.running && <p className="settings-note">Pause replay on Overview to change recordings.</p>}</div></section>
        <section className="panel"><div className="panel-heading"><div><h2>Prototype information</h2><p>Data and operational boundaries</p></div><Database size={19} /></div><div className="settings-body"><dl><dt>Dataset</dt><dd>WDSEventDB · {settings?.dataset_recordings || recordings.length} recordings</dd><dt>Storage</dt><dd>SQLite</dd><dt>Measurements</dt><dd>Real physical-testbed readings</dd><dt>Zone names</dt><dd>Illustrative deployment categories</dd><dt>Crew assignments</dt><dd>Configured demonstration roster</dd><dt>ML training</dt><dd>Separate pipeline</dd></dl><a className="text-link" href="https://github.com/Moazeni-s-Concise-Lab/WDSEventDB" target="_blank" rel="noreferrer">Dataset documentation<ArrowUpRight size={14} /></a></div></section>
      </div>}
      <footer className="page-footer"><span><ShieldCheck size={13} />Inspection actions require operator approval.</span><span>Water Guardian <span className="divider-dot">·</span> Prototype v0.1</span></footer>
      </>}
      </div>
    </main>
    {toast && <div className="toast" role="status"><CircleHelp size={17} /><span>{toast}</span><button aria-label="Dismiss notification" onClick={() => setToast("")}><X size={16} /></button></div>}
    <Dialog open={!!order} onOpenChange={open => { if (!open) setOrder(null); }} title={order?.title || "Inspection task"} description={order ? `${order.id} · ${nameFor(order.asset_id)}` : undefined}>
      {order && <><div className="dialog-body"><div className="order-meta"><Badge status={order.status} /><span className="priority-text">{order.priority} priority</span></div><h3>Inspection instructions</h3><p>{order.instructions}</p><dl><dt>Proposed crew</dt><dd>{data?.crews.find(c => c.id === order.crew_id)?.name || "No eligible crew assigned"}</dd><dt>Operational mode</dt><dd>Demonstration task tracking</dd></dl>{order.status === "pending_approval" && <label className="field-label">Decision note<textarea placeholder="Optional context for your decision" value={decisionNote} onChange={e => setDecisionNote(e.target.value)} /></label>}{order.decision_note && <p className="decision-note">Operator note: {order.decision_note}</p>}</div><div className="dialog-actions">{order.status === "pending_approval" ? <><Button variant="destructive" disabled={!!busy} onClick={() => decide("reject")}><X size={15} />Reject</Button><Button disabled={!!busy || !order.crew_id} onClick={() => decide("approve")}>{busy ? <Loader2 size={15} className="spin" /> : <Check size={15} />}Approve inspection</Button></> : order.status === "approved" || order.status === "in_progress" ? <Button disabled={!!busy} onClick={async () => { const r = await act("status", `/api/work-orders/${order.id}/status?status=${order.status === "approved" ? "in_progress" : "completed"}`, undefined, "PATCH"); if (r) setOrder(null); }}><Check size={15} />{order.status === "approved" ? "Mark in progress" : "Mark completed"}</Button> : <Button variant="outline" onClick={() => setOrder(null)}>Close</Button>}</div></>}
    </Dialog>
  </div>;
}



