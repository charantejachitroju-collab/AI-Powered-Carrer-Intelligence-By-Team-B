import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCheck, LoaderCircle, Search, Settings2, X,
} from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api, jsonRequest } from "./api";
import marketData from "../market_data.json";

const PACKAGE_ROLE_MATCHERS = [
  ["Agentic AI Engineer", /\bagentic\b/i], ["MLOps Engineer", /\bmlops\b/i],
  ["NLP Engineer", /\bnlp\b|natural language processing/i],
  ["AI/ML Engineer", /\bai\s*\/?\s*ml\b|machine learning|artificial intelligence|\bai engineer\b|copilot|generative ai|\bllm\b/i],
  ["Data Scientist", /\bdata scientist\b/i], ["Data Analyst", /\bdata analyst\b/i],
  ["Business Intelligence Analyst", /business intelligence|\bbi analyst\b/i], ["Data Engineer", /\bdata engineer\b/i],
  ["Cybersecurity Analyst", /cyber\s?security|security analyst|information security/i],
  ["Database Administrator", /database administrator|\bdba\b/i], ["Product Manager", /\bproduct manager\b/i],
  ["UX Designer", /\bux\b|user experience/i], ["Mobile Application Developer", /\bmobile\b|\bandroid\b|\bios\b/i],
  ["QA Engineer", /\bqa\b|quality assurance|test engineer/i],
  ["DevOps Engineer", /\bdevops\b|site reliability|\bsre\b|reliability engineer/i],
  ["Cloud Engineer", /\bcloud engineer\b/i], ["Automation Engineer", /\bautomation engineer\b/i],
  ["Backend Developer", /back[ -]?end|server[ -]?side/i], ["Frontend Developer", /front[ -]?end|ui developer/i],
  ["Full-Stack Developer", /full[ -]?stack|software engineer|software developer|application developer/i],
];
const PAGE_SIZE = 10;
const TABS = [
  { label: "All", value: "all", status: "all" },
  { label: "New", value: "new", status: "unread" },
  { label: "Best match", value: "best", status: "all" },
];
const DEFAULT_PREFERENCES = {
  job_matches: true, internships: true, application_updates: true,
  interview_reminders: true, deadline_reminders: true, ai_insights: true,
  email_notifications: false, in_app_notifications: true,
  preferred_roles: [], preferred_locations: [], work_modes: ["Remote", "Hybrid", "On-site"],
  job_types: ["Internship", "Full-time", "Part-time", "Contract"], minimum_match_percentage: 70,
};

export default function NotificationsPage({ notify, setNotificationCount }) {
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(TABS[0]);
  const [query, setQuery] = useState(() => searchParams.get("search") || "");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sort, setSort] = useState("newest");
  const [records, setRecords] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);
  const [savingPreference, setSavingPreference] = useState("");
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState("");
  const [liveProviderReady, setLiveProviderReady] = useState(false);
  const [jobSources, setJobSources] = useState([]);
  const [providerSetupPartial, setProviderSetupPartial] = useState(false);
  const requestId = useRef(0);
  const recordsRef = useRef([]);
  const initialJobLoad = useRef(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => { setQuery(searchParams.get("search") || ""); }, [searchParams]);

  const queryString = useMemo(() => {
    const params = new URLSearchParams({
      category: activeTab.value === "best" ? "job_match" : "all",
      status: activeTab.status,
      search: debouncedQuery,
      sort,
      limit: String(PAGE_SIZE),
    });
    return params.toString();
  }, [activeTab, debouncedQuery, sort]);

  const fetchPage = useCallback(async ({ reset = false, silent = false } = {}) => {
    const request = ++requestId.current;
    if (reset) {
      if (!silent) setLoading(true);
      setError("");
    } else setLoadingMore(true);
    try {
      const offset = reset ? 0 : recordsRef.current.length;
      const data = await api(`/notifications?${queryString}&offset=${offset}`);
      if (request !== requestId.current) return;
      const nextRecords = reset ? data.notifications : [...recordsRef.current, ...data.notifications.filter(item => !recordsRef.current.some(old => old.id === item.id))];
      recordsRef.current = nextRecords;
      setRecords(nextRecords);
      setResult(data);
      setNotificationCount(data.unread || 0);
      setError("");
    } catch (failure) {
      if (request !== requestId.current) return;
      setError(failure.message || "Unable to load notifications.");
    } finally {
      if (request === requestId.current) {
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, [queryString, setNotificationCount]);

  useEffect(() => { fetchPage({ reset: true }); }, [fetchPage]);

  const seedSampleJobs = useCallback(async ({ silent = false } = {}) => {
    setJobLoading(true);
    setJobError("");
    try {
      const data = await api("/notifications/sample-jobs/seed", { method: "POST" });
      await fetchPage({ reset: true, silent: true });
      if (!silent) notify(data.created ? `${data.created} sample job alerts added.` : `${data.total} sample job alerts are already loaded.`);
    } catch (failure) {
      setJobError(failure.message || "Unable to load sample job alerts.");
    } finally { setJobLoading(false); }
  }, [fetchPage, notify]);

  const refreshJobs = useCallback(async ({ silent = false } = {}) => {
    setJobLoading(true);
    setJobError("");
    try {
      const data = await api("/notifications/jobs/refresh", { method: "POST" });
      setJobSources(data.providers || []);
      setLiveProviderReady(Boolean(data.providers?.length));
      await fetchPage({ reset: true, silent: true });
      if (!silent) notify(data.jobs ? `${data.jobs} live listings checked from ${data.source}.` : `No live listings returned by ${data.source}.`);
    } catch (failure) {
      setJobError(failure.message || "Unable to refresh live job listings.");
    } finally { setJobLoading(false); }
  }, [fetchPage, notify]);

  const initializeJobFeed = useCallback(async () => {
    setJobLoading(true);
    try {
      const status = await api("/notifications/jobs/provider-status");
      setProviderSetupPartial(!status.adzuna_configured && (status.app_id_present || status.app_key_present));
      setJobSources(status.providers || []);
      if (status.providers?.length) {
        setLiveProviderReady(true);
        await refreshJobs({ silent: true });
      } else {
        setLiveProviderReady(false);
        await seedSampleJobs({ silent: true });
      }
    } catch (failure) {
      setJobError(failure.message || "Unable to initialize the job feed.");
    } finally { setJobLoading(false); }
  }, [refreshJobs, seedSampleJobs]);

  useEffect(() => {
    if (initialJobLoad.current) return;
    initialJobLoad.current = true;
    initializeJobFeed();
  }, [initializeJobFeed]);

  // The current stack has no Supabase Realtime channel. Poll the authenticated
  // backend while this page is open so trusted backend inserts appear promptly.
  useEffect(() => {
    const poll = async () => {
      if (document.visibilityState !== "visible") return;
      try {
        const data = await api(`/notifications?${queryString}&offset=0`);
        const existingIds = new Set(recordsRef.current.map(item => item.id));
        const added = data.notifications.filter(item => !existingIds.has(item.id));
        if (added.length) {
          const next = [...added, ...recordsRef.current.filter(item => !added.some(fresh => fresh.id === item.id))].slice(0, Math.max(PAGE_SIZE, recordsRef.current.length));
          recordsRef.current = next;
          setRecords(next);
          notify(added.length === 1 ? "A new notification arrived." : `${added.length} new notifications arrived.`);
        }
        setResult(data);
        setNotificationCount(data.unread || 0);
      } catch { /* Keep the current page visible; the next poll or manual refresh can recover. */ }
    };
    const timer = window.setInterval(poll, 30_000);
    return () => window.clearInterval(timer);
  }, [queryString, notify, setNotificationCount]);

  const ensurePreferences = async () => {
    setShowSettings(value => !value);
    if (preferencesLoaded) return;
    try {
      const data = await api("/notifications/preferences");
      setPreferences({ ...DEFAULT_PREFERENCES, ...data });
      setPreferencesLoaded(true);
    } catch (failure) { notify(`Unable to load notification settings: ${failure.message}`); }
  };

  const savePreference = async (key, value) => {
    const next = { ...preferences, [key]: value };
    setPreferences(next);
    setSavingPreference(key);
    try {
      const data = await api("/notifications/preferences", jsonRequest("PATCH", { [key]: value }));
      setPreferences({ ...DEFAULT_PREFERENCES, ...data });
      notify("Notification preference saved.");
    } catch (failure) {
      setPreferences(preferences);
      notify(`Unable to save this preference: ${failure.message}`);
    } finally { setSavingPreference(""); }
  };

  const markRead = async item => {
    if (item.is_read) return;
    try {
      await api(`/notifications/${encodeURIComponent(item.id)}/read`, { method: "PATCH" });
      const next = recordsRef.current.map(row => row.id === item.id ? { ...row, is_read: true } : row);
      recordsRef.current = next;
      setRecords(next);
      await fetchPage({ reset: true, silent: true });
    } catch (failure) { notify(`Unable to update notification: ${failure.message}`); }
  };

  const markAllRead = async () => {
    try {
      const response = await api("/notifications/read-all", { method: "POST" });
      const next = recordsRef.current.map(row => ({ ...row, is_read: true }));
      recordsRef.current = next;
      setRecords(next);
      await fetchPage({ reset: true, silent: true });
      notify(response.updated ? `${response.updated} notifications marked as read.` : "You are all caught up.");
    } catch (failure) { notify(`Unable to mark notifications as read: ${failure.message}`); }
  };

  const unreadCount = result?.unread || 0;
  const visibleRecords = records
    .filter(item => item.job)
    .sort((a, b) => activeTab.value === "best"
      ? (b.match_percentage ?? -1) - (a.match_percentage ?? -1)
      : (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * (sort === "oldest" ? 1 : -1));
  return <main className="job-alerts-page">
    <header className="job-alerts-header">
      <div className="flex flex-wrap items-center gap-3"><h2>Job alerts</h2><span className="job-alerts-unread">{unreadCount} new</span></div>
      <div className="job-alerts-actions">
        <button className="job-alerts-secondary" onClick={ensurePreferences}><Settings2 size={16}/>Notification settings</button>
        <button className="job-alerts-primary" onClick={markAllRead} disabled={!unreadCount}><CheckCheck size={16}/>Mark all as read</button>
      </div>
    </header>

    {showSettings && <section className="mb-5 rounded-2xl border border-violet-100 bg-white p-5 shadow-soft md:p-6">
      <div className="mb-4 flex items-start justify-between gap-3"><div><h3 className="font-bold">Notification preferences</h3><p className="mt-1 text-xs text-slate-500">Saved privately to your CareerInfinity account.</p></div><button aria-label="Close notification settings" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" onClick={() => setShowSettings(false)}><X size={17}/></button></div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {[["job_matches", "Job matches"], ["internships", "Internship alerts"], ["application_updates", "Application updates"], ["interview_reminders", "Interview reminders"], ["deadline_reminders", "Deadline reminders"], ["ai_insights", "AI career insights"], ["email_notifications", "Email notifications"], ["in_app_notifications", "In-app notifications"]].map(([key, label]) => <label key={key} className="flex min-h-12 items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2 text-xs font-semibold text-slate-700"><span>{label}</span><input type="checkbox" checked={Boolean(preferences[key])} disabled={savingPreference === key || !preferencesLoaded} onChange={event => savePreference(key, event.target.checked)} className="h-4 w-4 accent-violet-600"/></label>)}
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="grid gap-1 text-[11px] font-semibold text-slate-600">Preferred roles <input value={(preferences.preferred_roles || []).join(", ")} placeholder="Python developer, AI engineer" onChange={event => setPreferences(current => ({ ...current, preferred_roles: event.target.value.split(",").map(value => value.trim()).filter(Boolean) }))} onBlur={() => savePreference("preferred_roles", preferences.preferred_roles || [])} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-xs font-normal" disabled={!preferencesLoaded}/></label>
        <label className="grid gap-1 text-[11px] font-semibold text-slate-600">Preferred locations <input value={(preferences.preferred_locations || []).join(", ")} placeholder="Bengaluru, Remote" onChange={event => setPreferences(current => ({ ...current, preferred_locations: event.target.value.split(",").map(value => value.trim()).filter(Boolean) }))} onBlur={() => savePreference("preferred_locations", preferences.preferred_locations || [])} className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-xs font-normal" disabled={!preferencesLoaded}/></label>
        <label className="grid gap-1 text-[11px] font-semibold text-slate-600">Minimum match: {preferences.minimum_match_percentage}% <input type="range" min="0" max="100" step="5" value={preferences.minimum_match_percentage} onChange={event => setPreferences(current => ({ ...current, minimum_match_percentage: Number(event.target.value) }))} onMouseUp={event => savePreference("minimum_match_percentage", Number(event.currentTarget.value))} onTouchEnd={event => savePreference("minimum_match_percentage", Number(event.currentTarget.value))} onKeyUp={event => savePreference("minimum_match_percentage", Number(event.currentTarget.value))} className="mt-2 accent-violet-600" disabled={!preferencesLoaded}/></label>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {["Remote", "Hybrid", "On-site"].map(mode => <label key={mode} className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={(preferences.work_modes || []).includes(mode)} disabled={!preferencesLoaded} onChange={event => savePreference("work_modes", event.target.checked ? [...preferences.work_modes, mode] : preferences.work_modes.filter(value => value !== mode))} className="accent-violet-600"/>{mode}</label>)}
        {["Internship", "Full-time", "Part-time", "Contract"].map(kind => <label key={kind} className="inline-flex items-center gap-2 text-xs text-slate-600"><input type="checkbox" checked={(preferences.job_types || []).includes(kind)} disabled={!preferencesLoaded} onChange={event => savePreference("job_types", event.target.checked ? [...preferences.job_types, kind] : preferences.job_types.filter(value => value !== kind))} className="accent-violet-600"/>{kind}</label>)}
      </div>
      <p className="mt-3 text-[11px] text-slate-400">Email delivery is not connected yet; the saved email setting does not send messages.</p>
    </section>}

    <section className="job-feed-control">
      <span>{liveProviderReady ? `Live listings · ${jobSources.join(", ") || "job providers"}` : "Sample roles · not live vacancies"}</span>
      <button onClick={() => liveProviderReady ? refreshJobs() : seedSampleJobs()} disabled={jobLoading}>{jobLoading && <LoaderCircle size={14} className="animate-spin"/>}{jobLoading ? "Loading…" : liveProviderReady ? "Refresh jobs" : "Load sample jobs"}</button>
      {providerSetupPartial && <p>Add both Adzuna credentials to the backend .env and restart the server to enable live listings.</p>}
      {jobError && <p role="alert">{jobError}</p>}
    </section>

    <div className="job-alerts-tools">
      <label className="job-alerts-search"><Search size={16}/><span className="sr-only">Search job alerts</span><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search jobs"/></label>
      <label className="job-alerts-sort"><span>Sort</span><select value={sort} onChange={event => setSort(event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>
    </div>

    <div className="job-alerts-tabs" role="tablist" aria-label="Job alert filters">
      {TABS.map(tab => <button key={tab.value} role="tab" aria-selected={activeTab.value === tab.value} onClick={() => setActiveTab(tab)}>{tab.label}{tab.value === "new" && unreadCount > 0 ? ` · ${unreadCount}` : ""}</button>)}
    </div>

    {error && <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-100 bg-rose-50 p-4 text-sm text-rose-700" role="alert"><span>{error}</span><button onClick={() => fetchPage({ reset: true })} className="font-bold underline">Retry</button></div>}
    {loading && !records.length ? <div className="job-alerts-skeleton" aria-label="Loading job alerts">{[0, 1, 2].map(index => <div key={index}/>)}</div> : visibleRecords.length ? <>
      <div className="job-alert-list" aria-live="polite" aria-busy={loading || loadingMore}>
        {visibleRecords.map(item => {
          const job = item.job;
          const rawPay = formatPackage(job, item.title).replace(/^Package:\s*/i, "").replace(/\(project estimate\)/i, "(estimate)");
          const highMatch = Number(item.match_percentage) >= Math.max(75, Number(preferences.minimum_match_percentage) || 0);
          return <article key={item.id} className="job-alert-card">
            {highMatch && <span className="job-match-pill">Good match for you</span>}
            <h3>{item.title}</h3>
            <p className="job-alert-company">{item.company_name || "Company not disclosed"}{job.location ? ` · ${job.location}` : ""}</p>
            <p className="job-alert-pay">{rawPay}</p>
            {job.job_url ? <a className="job-apply" href={job.job_url} target="_blank" rel="noreferrer" onClick={() => markRead(item)}>Apply</a> : <button className="job-apply" disabled>Apply unavailable</button>}
          </article>;
        })}
      </div>
      <p className="job-alert-hint">Tap Apply to open the job page</p>
      {result?.has_more && <button onClick={() => fetchPage()} disabled={loadingMore} className="job-alert-load-more">{loadingMore && <LoaderCircle size={14} className="animate-spin"/>}Load 10 more</button>}
    </> : !error && <div className="job-alert-empty">{query || activeTab.value !== "all" ? "No matching job alerts. Try another search or tab." : "No job alerts yet. New opportunities will appear here."}</div>}
  </main>;
}

function formatPackage(job, title) {
  if (job.salary_label) return `Package: ${job.salary_label}`;
  if (job.salary_min != null || job.salary_max != null) {
    const currency = job.salary_currency === "INR" ? "₹" : job.salary_currency ? `${job.salary_currency} ` : "";
    const format = value => `${currency}${Number(value).toLocaleString("en-IN")}`;
    const range = job.salary_min != null && job.salary_max != null ? `${format(job.salary_min)}–${format(job.salary_max)}` : format(job.salary_min ?? job.salary_max);
    return `Package: ${range}${job.salary_period ? ` / ${job.salary_period}` : " (period not specified by source)"}`;
  }
  const matchText = `${title || ""} ${job.description || ""}`;
  const roleName = PACKAGE_ROLE_MATCHERS.find(([_, pattern]) => pattern.test(matchText))?.[0];
  const role = marketData.roles.find(entry => entry.title === roleName);
  const range = role?.salary_lpa?.replace(/\s*\(sample\)\s*$/i, "");
  return range ? `Package: ${range} (project estimate)` : "Package: Estimate unavailable";
}

