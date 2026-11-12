import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ScanLine,
  LayoutGrid,
  Copy,
  Layers,
  Activity,
  ArrowUpRight,
  ArrowRight,
  Upload,
  Search,
  ChevronDown,
  X,
  Check,
  FileText,
  SlidersHorizontal,
  Loader2,
  Plus,
  Github,
  RefreshCw,
  ZoomIn,
  Menu,
  Download,
  AlertCircle,
  Play,
  LogOut,
} from "lucide-react";
import {
  api,
  asset,
  post,
  type Page,
  type Batch,
  type Doc,
  type Run,
  type Pair,
  type Metrics,
} from "./api";
import "./styles.css";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";

type View = "Library" | "Duplicates" | "Layout clusters" | "Pipeline";
const nav = [
  { name: "Library", icon: LayoutGrid },
  { name: "Duplicates", icon: Copy },
  { name: "Layout clusters", icon: Layers },
  { name: "Pipeline", icon: Activity },
] as const;

function App() {
  const [view, setView] = useState<View>("Library");
  const [batches, setBatches] = useState<Batch[]>([]),
    [batch, setBatch] = useState("");
  const [pages, setPages] = useState<Page[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0);
  const [docs, setDocs] = useState<Doc[]>([]),
    [metrics, setMetrics] = useState<Metrics | null>(null);
  const [pairs, setPairs] = useState<Pair[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [runId, setRunId] = useState("");
  const [query, setQuery] = useState(""),
    [search, setSearch] = useState(""),
    [busy, setBusy] = useState("");
  const [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [upload, setUpload] = useState(false);
  const [selected, setSelected] = useState<Page | null>(null),
    [similar, setSimilar] = useState<Page[]>([]),
    [compare, setCompare] = useState<Pair | null>(null);
  const [eps, setEps] = useState(0.11),
    [minimum, setMinimum] = useState(2),
    [menu, setMenu] = useState(false);
  const [config, setConfig] = useState<{
      demo: boolean;
      auth_required: boolean;
    } | null>(null),
    [logged, setLogged] = useState(!!sessionStorage.getItem("doculens-token"));
  const [token, setToken] = useState(""),
    [uploadLog, setUploadLog] = useState<string[]>([]),
    [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const run = runs.find((r) => r.id === runId) || runs[0];
  const currentBatch = batches.find((b) => b.id === batch);
  const working = docs.some((d) =>
    ["QUEUED", "PROCESSING", "RETRY_WAIT"].includes(d.status),
  );

  useEffect(() => {
    if (config) return;
    let active = true;
    const connect = () =>
      api<typeof config>("/v1/config")
        .then((c) => {
          if (active) {
            setConfig(c);
            setError("");
          }
        })
        .catch(() => {
          if (active) setError("Cannot reach the API. Reconnecting…");
        });
    connect();
    const timer = setInterval(connect, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [config]);
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query);
      setOffset(0);
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 4500);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  const refresh = useCallback(async () => {
    if (!config || (config.auth_required && !logged)) return;
    const [bs, m] = await Promise.all([
      api<Batch[]>("/v1/batches"),
      api<Metrics>("/v1/metrics"),
    ]);
    setBatches(bs);
    setMetrics(m);
    if (!batch && bs.length) {
      setBatch(bs[0].id);
      return;
    }
    if (batch) {
      const [p, b, r] = await Promise.all([
        api<{ pages: Page[]; total: number }>(
          `/v1/pages?batch_id=${batch}&offset=${view === "Library" ? offset : 0}&limit=${view === "Layout clusters" ? 100 : 60}&q=${encodeURIComponent(view === "Library" ? search : "")}`,
        ),
        api<{ documents: Doc[] }>(`/v1/batches/${batch}`),
        api<Run[]>(`/v1/cluster-runs?batch_id=${batch}`),
      ]);
      if (view === "Layout clusters" && p.total > 100) {
        const remaining = await Promise.all(
          Array.from(
            { length: Math.ceil(Math.min(p.total, 500) / 100) - 1 },
            (_, i) =>
              api<{ pages: Page[] }>(
                `/v1/pages?batch_id=${batch}&offset=${(i + 1) * 100}&limit=100`,
              ),
          ),
        );
        setPages([...p.pages, ...remaining.flatMap((result) => result.pages)]);
      } else {
        setPages(p.pages);
      }
      setTotal(p.total);
      setDocs(b.documents);
      setRuns(r);
    }
  }, [batch, offset, search, config, logged, view]);
  useEffect(() => {
    let active = true;
    const go = () =>
      refresh().catch((e) => {
        if (active) setError(e.message);
      });
    go();
    const timer = setInterval(go, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [refresh]);
  useEffect(() => {
    setPairs([]);
    if (view === "Duplicates" && batch && !working) {
      setBusy("Finding candidates");
      api<{ pairs: Pair[] }>(`/v1/duplicates?batch_id=${batch}`)
        .then((p) => setPairs(p.pairs))
        .catch((e) => setError(e.message))
        .finally(() => setBusy(""));
    }
  }, [view, batch, working]);
  useEffect(() => {
    setSimilar([]);
    if (selected)
      api<Page[]>(`/v1/pages/${selected.id}/similar`)
        .then(setSimilar)
        .catch((e) => setError(e.message));
  }, [selected]);
  useEffect(() => {
    const close = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setSelected(null);
        setCompare(null);
        setUpload(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  async function action(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function seed() {
    await action("Loading sample collection", async () => {
      const b = await post<Batch>("/v1/demo");
      setBatch(b.id);
      setView("Library");
      setToast(
        "16 synthetic pages queued. Your collection will appear as it processes.",
      );
      await refresh();
    });
  }
  async function clustering() {
    await action("Clustering layouts", async () => {
      const r = await post<Run>("/v1/cluster-runs", {
        batch_id: batch,
        eps,
        min_samples: minimum,
      });
      setRunId(r.id);
      setRuns((rs) => [r, ...rs]);
      setToast(
        `${r.cluster_count} layout groups found; ${r.noise_count} unassigned pages.`,
      );
    });
  }
  async function uploadFiles(files: FileList | File[]) {
    const list = Array.from(files);
    if (!list.length) return;
    if (list.length > 100) {
      setError("Choose at most 100 files per batch.");
      return;
    }
    setUploadLog([]);
    await action("Uploading documents", async () => {
      const b = await post<Batch>("/v1/batches", {
        name: `Upload · ${new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })} ${new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`,
      });
      setBatch(b.id);
      setOffset(0);
      for (const f of list) {
        try {
          if (!["image/png", "image/jpeg", "application/pdf"].includes(f.type))
            throw new Error("Unsupported format");
          if (f.size > 20 * 1024 * 1024) throw new Error("Exceeds 20 MB");
          const ticket = await post<{ id: string; upload_url: string }>(
            "/v1/uploads/presign",
            { batch_id: b.id, filename: f.name, mime: f.type, size: f.size },
          );
          const res = await fetch(asset(ticket.upload_url), {
            method: "PUT",
            headers: { "Content-Type": f.type },
            body: f,
          });
          if (!res.ok) throw new Error(`Upload failed (${res.status})`);
          await post(`/v1/uploads/${ticket.id}/complete`);
          setUploadLog((log) => [...log, `✓ ${f.name} — queued`]);
        } catch (e) {
          setUploadLog((log) => [
            ...log,
            `! ${f.name} — ${(e as Error).message}`,
          ]);
        }
      }
      setView("Library");
      await refresh();
    });
  }
  const pageCard = (p: Page, index = 0) => (
    <button
      className="page-card"
      key={p.id}
      onClick={() => setSelected(p)}
      style={{ animationDelay: `${Math.min(index, 8) * 30}ms` }}
    >
      <div className={`paper-stage tint-${index % 3}`}>
        <img
          src={asset(p.thumbnail_url)}
          alt={`Preview of ${p.filename}, page ${p.page_no}`}
          loading="lazy"
        />
        <span className="zoom">
          <ZoomIn size={17} />
        </span>
        {p.similarity !== undefined && (
          <span className="score">
            {(p.similarity * 100).toFixed(1)}% similar
          </span>
        )}
      </div>
      <div className="page-caption">
        <FileText size={16} />
        <strong>{p.filename}</strong>
        <span>↗</span>
      </div>
      <div className="page-meta">
        <span>
          Page {p.page_no} <b>·</b> {p.width} × {p.height}
        </span>
        <i>
          <Check size={11} /> Indexed
        </i>
      </div>
    </button>
  );

  if (config?.auth_required && !logged)
    return (
      <main className="login">
        <ScanLine size={40} />
        <h1>Your document workspace.</h1>
        <p>Enter your workspace access token to continue.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sessionStorage.setItem("doculens-token", token);
            setLogged(true);
          }}
        >
          <label>
            Access token
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
            />
          </label>
          <button className="primary">
            Open DocuLens <ArrowRight size={16} />
          </button>
        </form>
        {error && <p role="alert">{error}</p>}
      </main>
    );
  return (
    <div className="app">
      <aside className={menu ? "sidebar open" : "sidebar"}>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("Library");
          }}
        >
          <span className="brand-icon">
            <ScanLine size={23} />
          </span>
          doculens<span className="brand-dot">.</span>
        </a>
        <div className="workspace">
          <span className="avatar">D</span>
          <div>
            <strong>Document workspace</strong>
            <small>{config?.demo ? "Local demo" : "Private workspace"}</small>
          </div>
          <ChevronDown size={14} />
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {nav.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={view === name ? "active" : ""}
              onClick={() => {
                setView(name);
                setMenu(false);
              }}
            >
              <Icon size={18} />
              {name}
              {name === "Library" && (
                <span className="nav-count">{metrics?.pages || 0}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="tiny-orbit">
            <Layers size={20} />
          </span>
          <strong>
            Less searching.
            <br />
            More seeing.
          </strong>
          <p>Let visual structure bring your documents together.</p>
          <a
            href="https://github.com/atbakhru/doculens"
            target="_blank"
            rel="noreferrer"
          >
            Explore the project <ArrowUpRight size={14} />
          </a>
        </div>
        <div className="sidebar-bottom">
          <span className="status-dot" />{" "}
          {metrics ? "Workspace connected" : "Connecting to API"}{" "}
          <span>v1.0</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <button
              className="icon-button mobile-menu"
              aria-label="Toggle navigation"
              onClick={() => setMenu(!menu)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">Workspace</span>
            <span className="slash">/</span>
            <strong>{view}</strong>
          </div>
          <div className="top-actions">
            <span className="environment">
              <span className="status-dot" />
              {config?.demo ? "DEMO WORKSPACE" : "PRIVATE WORKSPACE"}
            </span>
            <a
              aria-label="GitHub repository"
              href="https://github.com/atbakhru/doculens"
              target="_blank"
              rel="noreferrer"
            >
              <Github size={19} />
            </a>
            {logged && (
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={() => {
                  sessionStorage.removeItem("doculens-token");
                  setLogged(false);
                }}
              >
                <LogOut size={18} />
              </button>
            )}
            <span className="user-avatar">DL</span>
          </div>
        </header>
        <main className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">DOCUMENT INTELLIGENCE, AT A GLANCE</div>
              <h1>
                {view === "Library"
                  ? "A little order. A lot of clarity."
                  : view === "Duplicates"
                    ? "Same document. Another look."
                    : view === "Layout clusters"
                      ? "Structure finds its people."
                      : "From upload to understanding."}
              </h1>
              <p>
                {view === "Library"
                  ? "Your documents, connected by the way they look."
                  : view === "Duplicates"
                    ? "Review matching pages with visual evidence, side by side."
                    : view === "Layout clusters"
                      ? "Discover shared layouts with unsupervised visual clustering."
                      : "Follow every document through the processing pipeline."}
              </p>
            </div>
            <button
              className="primary"
              onClick={() => {
                setUpload(true);
                setUploadLog([]);
              }}
            >
              <Plus size={18} /> Upload documents
            </button>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <AlertCircle size={18} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={17} />
              </button>
            </div>
          )}
          <div className="stats">
            <Stat
              icon={<FileText size={19} />}
              label="Pages indexed"
              value={metrics?.pages ?? "—"}
              detail={`${metrics?.documents || 0} source documents`}
            />
            <Stat
              icon={<Check size={19} />}
              label="Files processed"
              value={metrics?.complete ?? "—"}
              detail="Ready to explore"
            />
            <Stat
              icon={<Layers size={19} />}
              label="Layout groups"
              value={run?.cluster_count ?? "—"}
              detail={
                run ? "In this batch’s selected run" : "Run a layout analysis"
              }
            />
            <Stat
              icon={<Activity size={19} />}
              label="In the pipeline"
              value={metrics?.queued ?? "—"}
              detail={
                metrics?.failed
                  ? `${metrics.failed} need attention`
                  : "All systems ready"
              }
              live={working}
            />
          </div>
          {view === "Library" && (
            <>
              <section className="feature-banner">
                <div className="banner-illustration">
                  <div className="mini-paper p-one">
                    <i />
                    <i />
                    <i />
                    <i />
                  </div>
                  <div className="mini-paper p-two">
                    <i />
                    <i />
                    <i />
                    <i />
                  </div>
                  <div className="lens">
                    <ScanLine size={25} />
                  </div>
                </div>
                <div>
                  <span className="section-kicker">
                    A NEW PERSPECTIVE ON YOUR FILES
                  </span>
                  <h2>Similar on the page. Together in your library.</h2>
                  <p>
                    Find repeated scans, discover shared layouts, and see what
                    belongs together.
                  </p>
                </div>
                <button onClick={() => setView("Layout clusters")}>
                  Explore layout clusters <ArrowRight size={16} />
                </button>
              </section>
              <div className="section-head">
                <div>
                  <h2>
                    Document library <span className="pill">{total} pages</span>
                  </h2>
                  <p>A visual home for every page in your collection.</p>
                </div>
                <div className="toolbar">
                  <label className="search">
                    <Search size={16} />
                    <input
                      aria-label="Search documents"
                      placeholder="Find a document…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <BatchSelect
                    batches={batches}
                    batch={batch}
                    onChange={(id) => {
                      setBatch(id);
                      setOffset(0);
                      setRunId("");
                    }}
                  />
                </div>
              </div>
              {pages.length ? (
                <>
                  <div className="library-grid">{pages.map(pageCard)}</div>
                  <div className="pagination">
                    <span>
                      Showing {offset + 1}–
                      {Math.min(offset + pages.length, total)} of {total} pages
                    </span>
                    <div>
                      <button
                        disabled={!offset}
                        onClick={() => setOffset(Math.max(0, offset - 60))}
                      >
                        Previous
                      </button>
                      <button
                        disabled={offset + 60 >= total}
                        onClick={() => setOffset(offset + 60)}
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <Empty
                  icon={<FileText size={30} />}
                  title={
                    working
                      ? "Your collection is taking shape."
                      : search
                        ? "No documents match your search."
                        : "Your next clear view starts here."
                  }
                  text={
                    working
                      ? "Pages appear here as the worker finishes processing them."
                      : "Upload a document collection, or explore 16 synthetic pages with three distinct layouts."
                  }
                >
                  {config?.demo && !search && (
                    <button
                      className="primary"
                      onClick={seed}
                      disabled={!!busy || working}
                    >
                      <Play size={15} />
                      {busy || "Explore sample collection"}
                    </button>
                  )}
                </Empty>
              )}
            </>
          )}
          {view === "Duplicates" && (
            <>
              <div className="section-head">
                <div>
                  <h2>
                    Duplicate review{" "}
                    <span className="pill">{pairs.length} pairs</span>
                  </h2>
                  <p>
                    Exact means byte-identical. Near matches need your judgment.
                  </p>
                </div>
                <BatchSelect
                  batches={batches}
                  batch={batch}
                  onChange={setBatch}
                />
              </div>
              <div className="notice">
                <ScanLine size={17} />
                <span>
                  Similar layouts can contain different information. Geometric
                  agreement is evidence to review; no files are automatically
                  removed.
                </span>
              </div>
              {busy || working ? (
                <Empty
                  icon={<Loader2 className="spin" />}
                  title={busy || "Waiting for processing"}
                  text="Candidate pages are screened by perceptual hash and checked with SIFT + RANSAC."
                />
              ) : pairs.length ? (
                <div className="pairs-grid">
                  {pairs.map((pair) => (
                    <button
                      className="pair-card"
                      key={pair.id}
                      onClick={() => setCompare(pair)}
                    >
                      <div className="pair-images">
                        <img
                          src={asset(pair.left.thumbnail_url)}
                          alt={pair.left.filename}
                        />
                        <Copy size={22} />
                        <img
                          src={asset(pair.right.thumbnail_url)}
                          alt={pair.right.filename}
                        />
                      </div>
                      <div className="pair-detail">
                        <span className={`tag ${pair.kind}`}>
                          {pair.kind === "exact"
                            ? "Exact duplicate"
                            : "Review candidate"}
                        </span>
                        <span>
                          {pair.kind === "exact"
                            ? "SHA-256 match"
                            : `${Math.round(pair.inlier_ratio * 100)}% geometric agreement`}
                        </span>
                        <ArrowUpRight size={16} />
                      </div>
                      <p>
                        {pair.left.filename} ↔ {pair.right.filename}
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <Empty
                  icon={<Copy size={30} />}
                  title="No matching pairs found."
                  text="Upload repeated or slightly rotated scans in the same batch to compare them."
                />
              )}
            </>
          )}
          {view === "Layout clusters" && (
            <>
              <div className="section-head">
                <div>
                  <h2>Layout explorer</h2>
                  <p>
                    Groups describe visual structure. You give them meaning.
                  </p>
                </div>
                <BatchSelect
                  batches={batches}
                  batch={batch}
                  onChange={(id) => {
                    setBatch(id);
                    setRunId("");
                  }}
                />
              </div>
              <div className="cluster-controls">
                <SlidersHorizontal size={20} />
                <label>
                  Neighborhood distance{" "}
                  <input
                    aria-label="Neighborhood distance"
                    type="number"
                    min="0.01"
                    max="1"
                    step="0.01"
                    value={eps}
                    onChange={(e) => setEps(Number(e.target.value))}
                  />
                </label>
                <label>
                  Minimum pages{" "}
                  <input
                    aria-label="Minimum pages"
                    type="number"
                    min="2"
                    max="20"
                    value={minimum}
                    onChange={(e) => setMinimum(Number(e.target.value))}
                  />
                </label>
                <button
                  className="primary"
                  disabled={!total || working || !!busy}
                  onClick={clustering}
                >
                  {busy ? (
                    <Loader2 className="spin" size={16} />
                  ) : (
                    <Layers size={16} />
                  )}{" "}
                  {busy || "Find layout groups"}
                </button>
              </div>
              {run && (
                <div className="run-meta">
                  <span>
                    <span className="status-dot" /> {run.cluster_count} groups ·{" "}
                    {run.noise_count} unassigned · DBSCAN
                  </span>
                  <select
                    aria-label="Cluster run"
                    value={run.id}
                    onChange={(e) => setRunId(e.target.value)}
                  >
                    {runs.map((r) => (
                      <option key={r.id} value={r.id}>
                        Run {r.id.slice(0, 6)} ·{" "}
                        {new Date(r.created_at * 1000).toLocaleTimeString()}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {run ? (
                <>
                  {Array.from(new Set(Object.values(run.members)))
                    .sort((a, b) => a - b)
                    .map((label) => (
                      <section className="cluster-group" key={label}>
                        <div className="cluster-title">
                          <span
                            className={`cluster-symbol color-${(label + 3) % 3}`}
                          >
                            <Layers size={19} />
                          </span>
                          <div>
                            <h3>
                              {run.names[String(label)] ||
                                (label === -1
                                  ? "Unassigned pages"
                                  : `Layout cluster ${label + 1}`)}
                            </h3>
                            <small>
                              {
                                Object.values(run.members).filter(
                                  (l) => l === label,
                                ).length
                              }{" "}
                              pages ·{" "}
                              {label === -1
                                ? "Outside a dense neighborhood"
                                : "Shared visual structure"}
                            </small>
                          </div>
                          <button
                            className="text-button"
                            onClick={() => {
                              const name = prompt(
                                "Name this layout group",
                                run.names[String(label)] ||
                                  `Layout cluster ${label + 1}`,
                              );
                              if (name)
                                action("Renaming group", async () => {
                                  const r = await api<Run>(
                                    `/v1/clusters/${run.id}/${label}`,
                                    {
                                      method: "PATCH",
                                      body: JSON.stringify({ name }),
                                    },
                                  );
                                  setRuns((rs) =>
                                    rs.map((x) => (x.id === r.id ? r : x)),
                                  );
                                });
                            }}
                          >
                            Rename <ArrowUpRight size={13} />
                          </button>
                        </div>
                        <div className="cluster-grid">
                          {pages
                            .filter((p) => run.members[p.id] === label)
                            .map(pageCard)}
                        </div>
                      </section>
                    ))}
                  {total > pages.length && (
                    <p className="notice">
                      Showing the first {pages.length} pages. All{" "}
                      {Object.keys(run.members).length} pages are included in
                      this run.
                    </p>
                  )}
                </>
              ) : (
                <Empty
                  icon={<Layers size={30} />}
                  title="See the patterns in your collection."
                  text="Run DBSCAN to group similar page layouts. Every run saves its parameters and feature version."
                />
              )}
            </>
          )}
          {view === "Pipeline" && (
            <>
              <div className="pipeline-flow">
                {[
                  "Upload",
                  "Normalize",
                  "Extract features",
                  "Index & review",
                ].map((s, i) => (
                  <React.Fragment key={s}>
                    <div>
                      <span>0{i + 1}</span>
                      <strong>{s}</strong>
                      <small>
                        {
                          [
                            "Private object storage",
                            "Bounded PDF / image rendering",
                            "SIFT + visual words + layout",
                            "Search, duplicates, DBSCAN",
                          ][i]
                        }
                      </small>
                    </div>
                    {i < 3 && <ArrowRight size={18} />}
                  </React.Fragment>
                ))}
              </div>
              <div className="section-head">
                <div>
                  <h2>Processing activity</h2>
                  <p>
                    Durable jobs, bounded retries, and a record of every source
                    file.
                  </p>
                </div>
                <BatchSelect
                  batches={batches}
                  batch={batch}
                  onChange={setBatch}
                />
              </div>
              <div className="job-table">
                <table>
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>State</th>
                      <th>Pages</th>
                      <th>Attempts</th>
                      <th>Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs.map((d) => (
                      <tr key={d.id}>
                        <td>
                          <FileText size={16} />
                          {d.filename}
                        </td>
                        <td>
                          <span
                            className={`job-state ${d.status.toLowerCase()}`}
                          >
                            {d.status.replaceAll("_", " ")}
                          </span>
                        </td>
                        <td>{d.processed_pages}</td>
                        <td>{d.attempts}</td>
                        <td>
                          {d.error ? (
                            <>
                              <span className="job-error">{d.error}</span>
                              <button
                                className="text-button"
                                onClick={() =>
                                  action("Retrying", async () => {
                                    await post(`/v1/uploads/${d.id}/retry`);
                                    await refresh();
                                  })
                                }
                              >
                                <RefreshCw size={13} /> Retry
                              </button>
                            </>
                          ) : d.status === "COMPLETE" ? (
                            "Indexed and ready"
                          ) : (
                            "Waiting for worker"
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!docs.length && (
                  <p className="table-empty">
                    No processing activity yet. Upload documents to begin.
                  </p>
                )}
              </div>
              <div className="engineering">
                <h3>Built to be explainable.</h3>
                <p>
                  SHA-256 identifies exact bytes. Perceptual hashing screens
                  near matches. SIFT and RANSAC measure geometric agreement. A
                  versioned 256-dimensional vector combines 128 visual words
                  with 128 spatial layout features.
                </p>
                <a
                  href="https://github.com/atbakhru/doculens/blob/main/docs/ARCHITECTURE.md"
                  target="_blank"
                  rel="noreferrer"
                >
                  Read the architecture <ArrowUpRight size={16} />
                </a>
                <button
                  onClick={() => {
                    const blob = new Blob(
                      [
                        JSON.stringify(
                          { metrics, documents: docs, cluster_runs: runs },
                          null,
                          2,
                        ),
                      ],
                      { type: "application/json" },
                    );
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "doculens-workspace-report.json";
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                >
                  <Download size={15} /> Export workspace report
                </button>
              </div>
            </>
          )}
          <footer>
            <span>
              <ScanLine size={14} /> Made for a clearer view.
            </span>
            <span>Visual similarity. Human judgment.</span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={18} />
          {toast}
        </div>
      )}
      {upload && (
        <Modal
          title="Bring your documents into focus."
          onClose={() => setUpload(false)}
        >
          <p className="modal-description">
            PNG, JPEG, and PDF · Up to 20 MB per file · 30 pages per PDF
          </p>
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              if (!busy) uploadFiles(e.dataTransfer.files);
            }}
          >
            <span className="upload-icon">
              <Upload size={28} />
            </span>
            <h3>Drop a collection here</h3>
            <p>Up to 100 files, one organized workspace.</p>
            <button
              className="primary"
              disabled={!!busy}
              onClick={() => fileInput.current?.click()}
            >
              {busy ? (
                <Loader2 className="spin" size={16} />
              ) : (
                <Plus size={16} />
              )}{" "}
              {busy || "Choose files"}
            </button>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept="image/png,image/jpeg,application/pdf"
              hidden
              onChange={(e) => {
                if (e.target.files) uploadFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </div>
          {uploadLog.length > 0 && (
            <div className="upload-log" role="status">
              {uploadLog.map((s, i) => (
                <p key={i} className={s.startsWith("!") ? "failed" : ""}>
                  {s}
                </p>
              ))}
              {!busy && (
                <button className="primary" onClick={() => setUpload(false)}>
                  View collection <ArrowRight size={16} />
                </button>
              )}
            </div>
          )}
          {config?.demo && (
            <button
              className="sample-link"
              disabled={!!busy}
              onClick={() => {
                setUpload(false);
                seed();
              }}
            >
              Just looking around? Load the sample collection{" "}
              <ArrowUpRight size={15} />
            </button>
          )}
        </Modal>
      )}
      {selected && (
        <Modal title={selected.filename} wide onClose={() => setSelected(null)}>
          <div className="inspector">
            <div className="full-preview">
              <img src={asset(selected.image_url)} alt={selected.filename} />
            </div>
            <div className="inspector-info">
              <span className="tag exact">
                <Check size={13} /> Indexed
              </span>
              <h2>A closer look.</h2>
              <dl>
                <dt>Source page</dt>
                <dd>{selected.page_no}</dd>
                <dt>Dimensions</dt>
                <dd>
                  {selected.width} × {selected.height}
                </dd>
                <dt>Processing time</dt>
                <dd>{selected.duration_ms.toFixed(0)} ms / page</dd>
                <dt>Feature model</dt>
                <dd className="mono">{selected.model_version}</dd>
                <dt>SHA-256</dt>
                <dd className="mono">{selected.sha256}</dd>
              </dl>
              <h3>Visually similar pages</h3>
              <p>
                Ranked by cosine similarity. Matching appearance does not imply
                matching content.
              </p>
              <div className="similar-list">
                {similar.slice(0, 5).map((p) => (
                  <button key={p.id} onClick={() => setSelected(p)}>
                    <img src={asset(p.thumbnail_url)} alt="" />
                    <span>
                      {p.filename}
                      <small>
                        {(p.similarity! * 100).toFixed(1)}% visual similarity
                      </small>
                    </span>
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Modal>
      )}
      {compare && (
        <Modal
          title="Look twice. Decide once."
          wide
          onClose={() => setCompare(null)}
        >
          <div className="compare-meta">
            <span className={`tag ${compare.kind}`}>
              {compare.kind === "exact"
                ? "Exact byte match"
                : "Near-duplicate candidate"}
            </span>
            <span>
              {compare.kind === "exact"
                ? "Matching SHA-256 digest"
                : `${compare.inliers} / ${compare.matches} matches agree · pHash distance ${compare.hash_distance}`}
            </span>
          </div>
          <div className="compare-grid">
            {[compare.left, compare.right].map((p) => (
              <div key={p.id}>
                <h3>{p.filename}</h3>
                <img src={asset(p.image_url)} alt={p.filename} />
              </div>
            ))}
          </div>
          <p className="notice">
            {compare.kind === "exact"
              ? "These page inputs have identical bytes."
              : "Geometric agreement can also occur between different documents sharing a template. Inspect the content before deciding."}{" "}
            Both originals are preserved.
          </p>
        </Modal>
      )}
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
  detail,
  live = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  detail: string;
  live?: boolean;
}) {
  return (
    <div className="stat">
      <div className="stat-top">
        <span>{label}</span>
        <i>{icon}</i>
      </div>
      <strong>
        {value}
        {live && <span className="pulse" />}
      </strong>
      <small>{detail}</small>
    </div>
  );
}
function BatchSelect({
  batches,
  batch,
  onChange,
}: {
  batches: Batch[];
  batch: string;
  onChange: (id: string) => void;
}) {
  return (
    <label className="batch-select">
      <Layers size={15} />
      <select
        aria-label="Select collection"
        value={batch}
        onChange={(e) => onChange(e.target.value)}
      >
        {!batches.length && <option>No collections yet</option>}
        {batches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      <ChevronDown size={13} />
    </label>
  );
}
function Empty({
  icon,
  title,
  text,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon}</span>
      <h2>{title}</h2>
      <p>{text}</p>
      {children}
    </div>
  );
}
function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    ref.current?.focus();
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = before;
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`modal ${wide ? "wide" : ""}`}
        onKeyDown={(e) => {
          if (e.key === "Tab") {
            const items = ref.current?.querySelectorAll<HTMLElement>(
              "button:not(:disabled),input,select,a[href]",
            );
            if (!items?.length) return;
            const first = items[0],
              last = items[items.length - 1];
            if (
              e.shiftKey &&
              (document.activeElement === first ||
                document.activeElement === ref.current)
            ) {
              e.preventDefault();
              last.focus();
            } else if (
              !e.shiftKey &&
              (document.activeElement === last ||
                document.activeElement === ref.current)
            ) {
              e.preventDefault();
              first.focus();
            }
          }
        }}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={21} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
