import { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import DriftTimeline from "./components/DriftTimeline";
import DriftDetailPanel from "./components/DriftDetailPanel";
import { mockDrifts } from "./mockDrifts";
import { fetchDrifts, analyzeRepo } from "./api/client";

// Main container component responsible for Mirror: repo-level summary + drift map
function App() {
  const [drifts, setDrifts] = useState([]);
  const [selectedDriftId, setSelectedDriftId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [repoUrl, setRepoUrl] = useState("https://github.com/git/git");
  const [maxCommits, setMaxCommits] = useState(30);
  const [maxDrifts, setMaxDrifts] = useState(5);
  const [analyzeStatus, setAnalyzeStatus] = useState("");

  useEffect(() => {
    async function loadInitialDrifts() {
      setLoading(true);
      setError(null);
      try {
        const items = await fetchDrifts();
        const list = items && items.length > 0 ? items : mockDrifts;
        setDrifts(list);
        if (list.length > 0) {
          setSelectedDriftId(list[0].id);
        }
      } catch (err) {
        console.error("Failed to fetch drifts, falling back to mock data:", err);
        setError("Could not load drifts from backend, showing mock data.");
        setDrifts(mockDrifts);
        if (mockDrifts.length > 0) {
          setSelectedDriftId(mockDrifts[0].id);
        }
      } finally {
        setLoading(false);
      }
    }

    loadInitialDrifts();
  }, []);

  const selectedDrift = drifts.find((d) => d.id === selectedDriftId) || null;

  // Helper function to format drift type (reused from DriftNode logic)
  function formatDriftType(driftType) {
    const typeMap = {
      architecture: "Architecture",
      api_contract: "API Contract",
      schema_db: "Schema / DB",
      config_env: "Config / Environment",
      ui_ux: "UI / UX",
      security_policy: "Security / Policy",
      process_governance: "Process / Governance",
      data_ml: "Data / ML",
    };
    return typeMap[driftType] || driftType.charAt(0).toUpperCase() + driftType.slice(1).replace(/_/g, " ");
  }

  // Compute health summary metrics (MMM: Mirror)
  function getTopDriftType(drifts) {
    const counts = {};
    for (const d of drifts) {
      if (!d.driftType) continue;
      counts[d.driftType] = (counts[d.driftType] || 0) + 1;
    }
    const entries = Object.entries(counts);
    if (entries.length === 0) return null;
    const [topType] = entries.sort((a, b) => b[1] - a[1])[0];
    return topType || null;
  }

  function getTopTeam(drifts) {
    const counts = {};
    for (const d of drifts) {
      (d.teams || []).forEach((team) => {
        counts[team] = (counts[team] || 0) + 1;
      });
    }
    const entries = Object.entries(counts);
    if (entries.length === 0) return null;
    const [topTeam] = entries.sort((a, b) => b[1] - a[1])[0];
    return topTeam || null;
  }

  const totalDrifts = drifts.length;
  const positiveCount = drifts.filter((d) => d.type === "positive").length;
  const negativeCount = drifts.filter((d) => d.type === "negative").length;
  const topDriftType = getTopDriftType(drifts);
  const topTeam = getTopTeam(drifts);

  async function handleAnalyzeRepo() {
    if (!repoUrl.trim()) {
      setAnalyzeStatus("Please enter a repository URL.");
      return;
    }
    setLoading(true);
    setError(null);
    setDrifts([]); // Clear previous drifts when starting new analysis
    setSelectedDriftId(null); // Clear selection
    setAnalyzeStatus("Analyzing repository for architectural drifts...");
    try {
      const driftsFromRepo = await analyzeRepo({
        repoUrl,
        maxCommits,
        maxDrifts,
      });
      if (!driftsFromRepo || driftsFromRepo.length === 0) {
        setAnalyzeStatus("No drifts detected (or response was empty).");
        setError("No drifts found. Try increasing max_commits or check if the repository has recent commits.");
        return;
      }
      setDrifts(driftsFromRepo);
      setSelectedDriftId(driftsFromRepo[0].id);
      setAnalyzeStatus(`Loaded ${driftsFromRepo.length} drifts from repo.`);
      setError(null); // Clear any previous errors
    } catch (err) {
      console.error("Error analyzing repo:", err);
      // Extract error message from axios error response
      const errorMessage = err.response?.data?.detail || err.message || "Failed to analyze repository.";
      setError(errorMessage);
      setAnalyzeStatus(`Analysis failed: ${errorMessage}`);
      setDrifts([]); // Clear drifts on error
      setSelectedDriftId(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />
      <section className="border-b border-slate-800 px-4 py-3 bg-slate-900/50">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <div className="flex-1 flex flex-col gap-2 md:flex-row md:items-center">
            <label className="text-sm text-slate-300 md:w-32">Repo URL</label>
            <input
              className="flex-1 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
            />
            <input
              className="w-24 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              type="number"
              min={1}
              value={maxCommits}
              onChange={(e) => setMaxCommits(Number(e.target.value) || 1)}
            />
            <input
              className="w-20 rounded-md bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-slate-100"
              type="number"
              min={1}
              value={maxDrifts}
              onChange={(e) => setMaxDrifts(Number(e.target.value) || 1)}
            />
            <button
              type="button"
              className="mt-2 md:mt-0 inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
              onClick={handleAnalyzeRepo}
              disabled={loading}
            >
              {loading ? "Analyzing..." : "Analyze Repo"}
            </button>
          </div>
          {analyzeStatus && (
            <p className="text-xs text-slate-400 mt-2 md:mt-0">{analyzeStatus}</p>
          )}
        </div>
      </section>
      {error && (
        <div className="px-4 py-2 text-sm text-amber-300 bg-amber-900/20 border-b border-amber-800">
          {error}
        </div>
      )}
      <main className="flex-1 flex flex-row gap-4 p-4">
        <section className="w-1/2 border-r border-slate-800 pr-4 overflow-y-auto">
          {/* MMM: MIRROR (repo-level health summary for this analysis window) */}
          {totalDrifts > 0 && (
            <div className="health-summary-bar flex flex-col gap-1 mb-4 p-3 rounded-lg bg-white/[0.02] border border-white/[0.08]">
              <div className="health-summary-main flex flex-wrap gap-2 items-baseline justify-between">
                <span className="health-summary-label text-xs uppercase tracking-wider opacity-70">
                  Repo Health
                </span>
                <span className="health-summary-value text-sm">
                  In this analysis window:{" "}
                  <strong>{totalDrifts}</strong> drifts (
                  <span className="health-summary-positive text-emerald-400">
                    {positiveCount} positive
                  </span>
                  ,{" "}
                  <span className="health-summary-negative text-rose-400">
                    {negativeCount} negative
                  </span>
                  )
                </span>
              </div>

              <div className="health-summary-secondary flex flex-wrap gap-2 mt-1 text-xs opacity-90">
                {topDriftType && (
                  <span className="health-summary-chip px-2 py-0.5 rounded-full border border-white/[0.12]">
                    Most affected area: {formatDriftType(topDriftType)}
                  </span>
                )}
                {topTeam && (
                  <span className="health-summary-chip px-2 py-0.5 rounded-full border border-white/[0.12]">
                    Most impacted team: {topTeam}
                  </span>
                )}
              </div>
            </div>
          )}
          <DriftTimeline
            drifts={drifts}
            selectedDriftId={selectedDriftId}
            onSelectDrift={setSelectedDriftId}
          />
        </section>
        <section className="w-1/2 pl-4 overflow-y-auto">
          {loading && (
            <div className="text-sm text-slate-400 mb-2">Loading...</div>
          )}
          <DriftDetailPanel drift={selectedDrift} />
        </section>
      </main>
    </div>
  );
}

export default App;
