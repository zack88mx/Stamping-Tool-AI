import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Archive,
  Calculator,
  ChevronRight,
  Database,
  FileUp,
  Gauge,
  Plus,
  Search,
  UploadCloud,
} from "lucide-react";
import { analyzePrint, createJob, fetchJobs, fileUrl, quoteSearch, quoteSearchUpload } from "./api";
import "./styles.css";

const JOB_FIELDS = [
  { name: "customer_name", label: "Customer Name", required: true },
  { name: "customer_type", label: "Customer Type" },
  { name: "industry", label: "Industry" },
  { name: "part_number", label: "Part Number", required: true },
  { name: "part_description", label: "Part Description", wide: true },
  { name: "material", label: "Material" },
  { name: "material_thickness", label: "Material Thickness", type: "number" },
  { name: "annual_volume", label: "Annual Volume", type: "number" },
  { name: "program_life", label: "Program Life", type: "number" },
  { name: "die_type", label: "Die Type" },
  { name: "number_of_stations", label: "Number of Stations", type: "number" },
  { name: "die_length", label: "Die Length", type: "number" },
  { name: "die_width", label: "Die Width", type: "number" },
  { name: "die_height", label: "Die Height", type: "number" },
  { name: "die_weight", label: "Die Weight", type: "number" },
  { name: "press_size", label: "Press Size" },
  { name: "quoted_price", label: "Quoted Price", type: "number" },
  { name: "awarded_price", label: "Awarded Price", type: "number" },
  { name: "actual_tool_build_hours", label: "Actual Tool Build Hours", type: "number" },
  { name: "design_hours", label: "Design Hours", type: "number" },
  { name: "cam_hours", label: "CAM Hours", type: "number" },
  { name: "cnc_hours", label: "CNC Hours", type: "number" },
  { name: "wire_hours", label: "Wire Hours", type: "number" },
  { name: "bench_hours", label: "Bench Hours", type: "number" },
  { name: "tryout_hours", label: "Tryout Hours", type: "number" },
  { name: "outsourced_cost", label: "Outsourced Cost", type: "number" },
  { name: "material_cost", label: "Material Cost", type: "number" },
  { name: "profit_margin", label: "Profit Margin", type: "number" },
  { name: "notes", label: "Notes", textarea: true, wide: true },
  { name: "lessons_learned", label: "Lessons Learned", textarea: true, wide: true },
];

const QUOTE_FIELDS = JOB_FIELDS.filter((field) =>
  [
    "customer_type",
    "industry",
    "material",
    "material_thickness",
    "annual_volume",
    "die_type",
    "number_of_stations",
    "die_length",
    "die_width",
    "die_height",
    "actual_tool_build_hours",
    "notes",
    "lessons_learned",
  ].includes(field.name),
);

const blankJob = Object.fromEntries(JOB_FIELDS.map((field) => [field.name, ""]));
const blankQuote = Object.fromEntries(QUOTE_FIELDS.map((field) => [field.name, ""]));
const NUMERIC_FIELDS = new Set(JOB_FIELDS.filter((field) => field.type === "number").map((field) => field.name));

function money(value) {
  if (value === null || value === undefined || value === "") return "-";
  return Number(value).toLocaleString(undefined, { style: "currency", currency: "USD" });
}

function valueForApi(name, value) {
  if (value === "" || value === null || value === undefined) return null;
  return NUMERIC_FIELDS.has(name) ? Number(value) : value;
}

function stepSize(job) {
  if (!job.step_bbox_length || !job.step_bbox_width || !job.step_bbox_height) return "";
  return `3D ${job.step_bbox_length} x ${job.step_bbox_width} x ${job.step_bbox_height}`;
}

function printSummary(job) {
  const pieces = [];
  if (job.print_gdt_callout_count) pieces.push(`${job.print_gdt_callout_count} GD&T`);
  if (job.print_tolerance_count) pieces.push(`${job.print_tolerance_count} tolerances`);
  if (job.print_tightest_tolerance) pieces.push(`tightest ${job.print_tightest_tolerance}`);
  return pieces.join(", ");
}

function useJobs() {
  const [jobs, setJobs] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(query = search) {
    setLoading(true);
    try {
      setJobs(await fetchJobs(query));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load("");
  }, []);

  return { jobs, search, setSearch, loading, load };
}

function Field({ field, value, onChange }) {
  const className = `field${field.wide ? " field-wide" : ""}`;
  return (
    <label className={className}>
      <span>{field.label}</span>
      {field.textarea ? (
        <textarea value={value} onChange={(event) => onChange(field.name, event.target.value)} />
      ) : (
        <input
          type={field.type || "text"}
          required={field.required}
          value={value}
          onChange={(event) => onChange(field.name, event.target.value)}
        />
      )}
    </label>
  );
}

function JobForm({ onSaved }) {
  const [form, setForm] = useState(blankJob);
  const [files, setFiles] = useState([]);
  const [saving, setSaving] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState("");

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const body = new FormData();
      Object.entries(form).forEach(([key, value]) => body.append(key, value));
      files.forEach((file) => body.append("files", file));
      await createJob(body);
      setForm(blankJob);
      setFiles([]);
      setMessage("Awarded job saved.");
      onSaved();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setSaving(false);
    }
  }

  async function chooseFiles(fileList) {
    const selected = Array.from(fileList || []);
    setFiles(selected);
    const print = selected.find((file) => /\.(pdf|png|jpe?g|webp|gif)$/i.test(file.name));
    if (!print) return;
    setAnalyzing(true);
    try {
      const analysis = await analyzePrint(print);
      setForm((current) => ({
        ...current,
        material: current.material || analysis.material || "",
        material_thickness: current.material_thickness || analysis.material_thickness || "",
        notes: current.notes || printSummary({
          print_gdt_callout_count: analysis.gdt_callout_count,
          print_tolerance_count: analysis.tolerance_count,
          print_tightest_tolerance: analysis.tightest_tolerance,
        }),
      }));
      setMessage(analysis.material || analysis.material_thickness ? "Print analyzed and material fields filled." : "Print analyzed. No material text found.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <form className="panel form-panel" onSubmit={submit}>
      <div className="panel-title">
        <Plus size={19} />
        <h2>Add Awarded Job</h2>
      </div>
      <div className="form-grid">
        {JOB_FIELDS.map((field) => (
          <Field key={field.name} field={field} value={form[field.name]} onChange={update} />
        ))}
      </div>
      <label className="dropzone">
        <UploadCloud size={22} />
        <span>{files.length ? `${files.length} file(s) selected` : "Upload PDF, image, STEP, or STP"}</span>
        <input
          type="file"
          multiple
          accept=".pdf,image/*,.step,.stp"
          onChange={(event) => chooseFiles(event.target.files)}
        />
      </label>
      <div className="actions">
        <button className="primary" type="submit" disabled={saving}>
          <FileUp size={18} />
          {saving ? "Saving" : "Save job"}
        </button>
        {analyzing && <span className="status">Analyzing print</span>}
        {message && <span className="status">{message}</span>}
      </div>
    </form>
  );
}

function JobsTable({ jobs, search, setSearch, loading, onSearch }) {
  return (
    <section className="panel table-panel">
      <div className="toolbar">
        <div className="panel-title">
          <Database size={19} />
          <h2>Awarded Jobs</h2>
        </div>
        <label className="search-box">
          <Search size={17} />
          <input
            placeholder="Search jobs"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") onSearch();
            }}
          />
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Customer</th>
              <th>Part</th>
              <th>Material</th>
              <th>Die</th>
              <th>Stations</th>
              <th>Awarded</th>
              <th>Build Hours</th>
              <th>Files</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="8">Loading jobs...</td></tr>
            ) : jobs.length === 0 ? (
              <tr><td colSpan="8">No awarded jobs found.</td></tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id}>
                  <td><strong>{job.customer_name}</strong><small>{[job.customer_type, job.industry].filter(Boolean).join(" / ") || "-"}</small></td>
                  <td>{job.part_number}<small>{job.part_description || ""}</small></td>
                  <td>{job.material || job.print_material_spec || "-"}<small>{job.material_thickness || job.print_thickness ? `${job.material_thickness || job.print_thickness} thick` : printSummary(job)}</small></td>
                  <td>{job.die_type || "-"}<small>{stepSize(job) || [job.die_length, job.die_width, job.die_height].filter(Boolean).join(" x ")}</small></td>
                  <td>{job.number_of_stations ?? "-"}</td>
                  <td>{money(job.awarded_price)}</td>
                  <td>{job.actual_tool_build_hours ?? "-"}</td>
                  <td>
                    <div className="file-list">
                      {job.files?.length ? job.files.map((file) => (
                        <a key={file.id} href={file.url || fileUrl(file.stored_filename)} target="_blank" rel="noreferrer">
                          {file.original_filename}
                        </a>
                      )) : "-"}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function QuoteSearch() {
  const [form, setForm] = useState(blankQuote);
  const [files, setFiles] = useState([]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setRunning(true);
    setError("");
    try {
      if (files.length) {
        const body = new FormData();
        Object.entries(form).forEach(([key, value]) => body.append(key, value));
        files.forEach((file) => body.append("files", file));
        setResult(await quoteSearchUpload(body));
      } else {
        const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, valueForApi(key, value)]));
        setResult(await quoteSearch(payload));
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setRunning(false);
    }
  }

  async function chooseFiles(fileList) {
    const selected = Array.from(fileList || []);
    setFiles(selected);
    const print = selected.find((file) => /\.(pdf|png|jpe?g|webp|gif)$/i.test(file.name));
    if (!print) return;
    setAnalyzing(true);
    try {
      const analysis = await analyzePrint(print);
      setForm((current) => ({
        ...current,
        material: current.material || analysis.material || "",
        material_thickness: current.material_thickness || analysis.material_thickness || "",
        notes: current.notes || printSummary({
          print_gdt_callout_count: analysis.gdt_callout_count,
          print_tolerance_count: analysis.tolerance_count,
          print_tightest_tolerance: analysis.tightest_tolerance,
        }),
      }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setAnalyzing(false);
    }
  }

  const range = result?.suggested_quote_range;

  return (
    <section className="quote-layout">
      <form className="panel quote-form" onSubmit={submit}>
        <div className="panel-title">
          <Calculator size={19} />
          <h2>New Quote Search</h2>
        </div>
        <div className="form-grid compact">
          {QUOTE_FIELDS.map((field) => (
            <Field key={field.name} field={field} value={form[field.name]} onChange={update} />
          ))}
        </div>
        <label className="dropzone">
          <Archive size={21} />
          <span>{files.length ? files.map((file) => file.name).join(", ") : "Attach new part print or STEP/STP file"}</span>
          <input
            type="file"
            multiple
            accept=".pdf,image/*,.step,.stp"
            onChange={(event) => chooseFiles(event.target.files)}
          />
        </label>
        <div className="actions">
          <button className="primary" type="submit" disabled={running}>
            <Gauge size={18} />
            {running ? "Scoring" : "Find matches"}
          </button>
          {analyzing && <span className="status">Analyzing print</span>}
          {error && <span className="status error">{error}</span>}
        </div>
      </form>

      <div className="results-stack">
        <div className="metric-row">
          <div className="metric">
            <span>Suggested low</span>
            <strong>{range ? money(range.low) : "-"}</strong>
          </div>
          <div className="metric">
            <span>Suggested high</span>
            <strong>{range ? money(range.high) : "-"}</strong>
          </div>
          <div className="metric">
            <span>Basis</span>
            <strong>{range?.basis_count ?? 0}</strong>
          </div>
        </div>
        <div className="panel">
          <div className="panel-title">
            <Search size={19} />
            <h2>Top Similar Jobs</h2>
          </div>
          <div className="match-list">
            {result?.results?.length ? result.results.map(({ job, score, breakdown }) => (
              <article className="match-card" key={job.id}>
                <div>
                  <h3>{job.part_number}</h3>
                  <p>{job.customer_name} - {job.material || job.print_material_spec || "Material open"} - {stepSize(job) || printSummary(job) || job.die_type || "Die type open"}</p>
                </div>
                <div className="match-score">{score}%</div>
                <div className="breakdown">
                  {Object.entries(breakdown).map(([key, value]) => (
                    <span key={key}>{key.replaceAll("_", " ")} {value.toFixed(1)}</span>
                  ))}
                </div>
                <div className="quote-line">
                  <span>Awarded {money(job.awarded_price)}</span>
                  <ChevronRight size={16} />
                </div>
              </article>
            )) : <div className="empty">Run a search to see the closest awarded jobs.</div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function App() {
  const [active, setActive] = useState("jobs");
  const jobsApi = useJobs();
  const stats = useMemo(() => {
    const totalAwarded = jobsApi.jobs.reduce((sum, job) => sum + Number(job.awarded_price || 0), 0);
    const avgHours = jobsApi.jobs.length
      ? jobsApi.jobs.reduce((sum, job) => sum + Number(job.actual_tool_build_hours || 0), 0) / jobsApi.jobs.length
      : 0;
    return { totalAwarded, avgHours };
  }, [jobsApi.jobs]);

  return (
    <main>
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">ST</div>
          <div>
            <h1>Stamping Tool AI</h1>
            <p>Tool and die quoting database</p>
          </div>
        </div>
        <nav>
          <button className={active === "jobs" ? "active" : ""} onClick={() => setActive("jobs")}>
            <Database size={18} /> Awarded Jobs
          </button>
          <button className={active === "quote" ? "active" : ""} onClick={() => setActive("quote")}>
            <Calculator size={18} /> New Quote Search
          </button>
        </nav>
        <div className="summary">
          <span>{jobsApi.jobs.length} jobs</span>
          <span>{money(stats.totalAwarded)} awarded</span>
          <span>{stats.avgHours.toFixed(1)} avg build hours</span>
        </div>
      </aside>

      <section className="content">
        {active === "jobs" ? (
          <>
            <JobForm onSaved={() => jobsApi.load("")} />
            <JobsTable {...jobsApi} onSearch={() => jobsApi.load(jobsApi.search)} />
          </>
        ) : (
          <QuoteSearch />
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
