import { useReducer, useState, useEffect } from "react";
import { resolveRepo, fetchBaselineStatus, generateBaseline, approveBaseline, suggestModuleMap, applyModuleMap, analyzeLocalRepo, createArchitectureSnapshot, listArchitectureSnapshots, getEffectiveConfig } from "../api/client";

const steps = [
  "Repo Input",
  "Resolve Repo",
  "Baseline Status",
  "Generate Baseline",
  "Approve Baseline",
];

function wizardReducer(state, action) {
  switch (action.type) {
    case "NEXT_STEP":
      return { step: Math.min(state.step + 1, steps.length - 1) };
    case "PREV_STEP":
      return { step: Math.max(state.step - 1, 0) };
    default:
      return state;
  }
}

function OnboardingWizard({ onClose, onActiveRepoUpdated }) {
  const [state, dispatch] = useReducer(wizardReducer, { step: 0 });
  const [repoUrl, setRepoUrl] = useState("");
  const [touched, setTouched] = useState(false);
  const [resolvedRepo, setResolvedRepo] = useState(null);
  const [resolveError, setResolveError] = useState(null);
  const [resolveLoading, setResolveLoading] = useState(false);
  const [baselineStatus, setBaselineStatus] = useState(null);
  const [baselineLoading, setBaselineLoading] = useState(false);
  const [baselineError, setBaselineError] = useState(null);
  const [generateResult, setGenerateResult] = useState(null);
  const [generateError, setGenerateError] = useState(null);
  const [generateLoading, setGenerateLoading] = useState(false);
  const [statusRefreshed, setStatusRefreshed] = useState(false);
  const [approvedBy, setApprovedBy] = useState("");
  const [approvalNote, setApprovalNote] = useState("");
  const [approveResult, setApproveResult] = useState(null);
  const [approveError, setApproveError] = useState(null);
  const [approveLoading, setApproveLoading] = useState(false);
  const [approveStatusRefreshed, setApproveStatusRefreshed] = useState(false);
  const [approvedByTouched, setApprovedByTouched] = useState(false);
  const [suggestMaxModules, setSuggestMaxModules] = useState(8);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestError, setSuggestError] = useState(null);
  const [suggestResult, setSuggestResult] = useState(null);
  const [appliedConfigDir, setAppliedConfigDir] = useState(null);
  const [applyConfigLabel, setApplyConfigLabel] = useState("suggested");
  const [applyLoading, setApplyLoading] = useState(false);
  const [applyError, setApplyError] = useState(null);
  const [applyResult, setApplyResult] = useState(null);
  const [localAnalysisMode, setLocalAnalysisMode] = useState("keywords");
  const [localAnalysisMaxCommits, setLocalAnalysisMaxCommits] = useState(50);
  const [localAnalysisMaxDrifts, setLocalAnalysisMaxDrifts] = useState(5);
  const [localAnalysisResult, setLocalAnalysisResult] = useState(null);
  const [localAnalysisError, setLocalAnalysisError] = useState(null);
  const [localAnalysisLoading, setLocalAnalysisLoading] = useState(false);
  const [snapshotLabel, setSnapshotLabel] = useState("v1");
  const [snapshotCreatedBy, setSnapshotCreatedBy] = useState("");
  const [snapshotNote, setSnapshotNote] = useState("");
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState(null);
  const [snapshotResult, setSnapshotResult] = useState(null);
  const [snapshotsLoading, setSnapshotsLoading] = useState(false);
  const [snapshotsError, setSnapshotsError] = useState(null);
  const [snapshotsList, setSnapshotsList] = useState(null);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState(null);
  const [effectiveLoading, setEffectiveLoading] = useState(false);
  const [effectiveError, setEffectiveError] = useState(null);
  const [effectiveResult, setEffectiveResult] = useState(null);
  const [effectiveConfigDir, setEffectiveConfigDir] = useState(null);
  const [guidedPathExpanded, setGuidedPathExpanded] = useState(false);
  const [lastLocalAnalysisMode, setLastLocalAnalysisMode] = useState(null);
  const [guidedPathCopied, setGuidedPathCopied] = useState(false);
  const [guidedPathCopyError, setGuidedPathCopyError] = useState(null);
  
  const currentStep = state.step;
  const currentStepTitle = steps[currentStep];
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === steps.length - 1;

  // Read from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("archdrift.onboarding.repoUrl");
      if (saved) {
        setRepoUrl(saved);
      }
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }, []);

  // Read selectedSnapshotId from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("archdrift.onboarding.snapshotId");
      if (saved && saved.trim()) {
        setSelectedSnapshotId(saved.trim());
      }
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }, []);

  // Write to localStorage on repoUrl change
  useEffect(() => {
    try {
      localStorage.setItem("archdrift.onboarding.repoUrl", repoUrl);
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }, [repoUrl]);

  // Clear resolved state when repoUrl changes
  useEffect(() => {
    setResolvedRepo(null);
    setResolveError(null);
    setResolveLoading(false);
  }, [repoUrl]);

  // Clear baseline state when resolvedRepo.repo_path changes
  useEffect(() => {
    setBaselineStatus(null);
    setBaselineError(null);
  }, [resolvedRepo?.repo_path]);

  // Clear generate state when resolvedRepo.repo_path changes
  useEffect(() => {
    setGenerateResult(null);
    setGenerateError(null);
    setGenerateLoading(false);
    setStatusRefreshed(false);
  }, [resolvedRepo?.repo_path]);

  // Clear approve state when resolvedRepo.repo_path changes
  useEffect(() => {
    setApproveResult(null);
    setApproveError(null);
    setApproveLoading(false);
    setApproveStatusRefreshed(false);
  }, [resolvedRepo?.repo_path]);

  // Clear suggest state when resolvedRepo.repo_path changes
  useEffect(() => {
    setSuggestResult(null);
    setSuggestError(null);
    setSuggestLoading(false);
  }, [resolvedRepo?.repo_path]);

  // Clear apply state when resolvedRepo.repo_path changes
  useEffect(() => {
    setAppliedConfigDir(null);
    setApplyLoading(false);
    setApplyError(null);
    setApplyResult(null);
    // Clear from localStorage
    try {
      localStorage.removeItem("archdrift.onboarding.configDir");
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }, [resolvedRepo?.repo_path]);

  // Clear snapshot picker state when resolvedRepo.repo_path changes
  useEffect(() => {
    setSnapshotsList(null);
    setSnapshotsError(null);
    setSnapshotsLoading(false);
    setSelectedSnapshotId(null);
    // Clear from localStorage
    try {
      localStorage.removeItem("archdrift.onboarding.snapshotId");
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }, [resolvedRepo?.repo_path]);

  // Clear effective config state when resolvedRepo.repo_path changes
  useEffect(() => {
    setEffectiveLoading(false);
    setEffectiveError(null);
    setEffectiveResult(null);
    setEffectiveConfigDir(null);
  }, [resolvedRepo?.repo_path]);

  // Clear effective config state when selectedSnapshotId changes
  useEffect(() => {
    setEffectiveResult(null);
    setEffectiveError(null);
    setEffectiveConfigDir(null);
  }, [selectedSnapshotId]);

  // Clear local analysis state when resolvedRepo.repo_path changes
  useEffect(() => {
    setLocalAnalysisResult(null);
    setLocalAnalysisError(null);
    setLocalAnalysisLoading(false);
  }, [resolvedRepo?.repo_path]);

  // Clear snapshot state when resolvedRepo.repo_path or appliedConfigDir changes
  useEffect(() => {
    setSnapshotLoading(false);
    setSnapshotError(null);
    setSnapshotResult(null);
  }, [resolvedRepo?.repo_path, appliedConfigDir]);

  // Helper function to persist active repo to localStorage
  function persistActiveRepo(repoUrlValue, resolvedRepoValue, baselineHash) {
    try {
      // Read existing activeRepo
      let existingActiveRepo = null;
      try {
        const existing = localStorage.getItem("archdrift.activeRepo");
        if (existing) {
          existingActiveRepo = JSON.parse(existing);
        }
      } catch (err) {
        // Invalid JSON, treat as no existing repo
      }

      // Determine baseline hash: preserve if same repoPath, otherwise use provided value
      let finalBaselineHash = baselineHash;
      if (existingActiveRepo && existingActiveRepo.repoPath === resolvedRepoValue.repo_path) {
        // Same repoPath: preserve existing hash if new hash is null/undefined
        if (baselineHash === null || baselineHash === undefined) {
          finalBaselineHash = existingActiveRepo.lastApprovedBaselineHash ?? null;
        }
      } else {
        // Different repoPath: use provided hash (or null if not provided)
        finalBaselineHash = baselineHash ?? null;
      }

      // Build activeRepo object
      const activeRepo = {
        repoUrl: repoUrlValue,
        repoPath: resolvedRepoValue.repo_path,
        repoName: resolvedRepoValue.repo_name,
        lastApprovedBaselineHash: finalBaselineHash,
      };

      // Write to localStorage
      localStorage.setItem("archdrift.activeRepo", JSON.stringify(activeRepo));

      // Call callback if provided
      if (onActiveRepoUpdated) {
        onActiveRepoUpdated(activeRepo);
      }
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }

  // Validation
  const repoUrlTrimmed = repoUrl.trim();
  const isValid = repoUrlTrimmed.length > 0;
  const showError = touched && !isValid;

  // Resolve repo handler
  async function handleResolveRepo() {
    setResolveLoading(true);
    setResolveError(null);
    setResolvedRepo(null);
    try {
      const result = await resolveRepo(repoUrlTrimmed);
      setResolvedRepo(result);
      // Persist active repo after successful resolve
      persistActiveRepo(repoUrlTrimmed, result, null);
      // Load appliedConfigDir from localStorage after resolve
      try {
        const savedConfigDir = localStorage.getItem("archdrift.onboarding.configDir");
        if (savedConfigDir && savedConfigDir.trim()) {
          setAppliedConfigDir(savedConfigDir.trim());
        }
      } catch (error) {
        // Fail silently if localStorage is unavailable
      }
    } catch (err) {
      setResolveError(err.message);
    } finally {
      setResolveLoading(false);
    }
  }

  // Fetch baseline status handler
  async function handleFetchBaselineStatus() {
    if (!resolvedRepo?.repo_path) {
      return;
    }
    setBaselineLoading(true);
    setBaselineError(null);
    setBaselineStatus(null);
    try {
      const result = await fetchBaselineStatus(resolvedRepo.repo_path, appliedConfigDir);
      setBaselineStatus(result);
    } catch (err) {
      setBaselineError(err.message);
    } finally {
      setBaselineLoading(false);
    }
  }

  // Auto-fetch baseline status when entering Step 3
  useEffect(() => {
    if (currentStep === 2 && resolvedRepo?.repo_path && !baselineLoading) {
      handleFetchBaselineStatus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, resolvedRepo?.repo_path]);

  // Auto-fetch baseline status when entering Step 5
  useEffect(() => {
    if (currentStep === 4 && resolvedRepo?.repo_path && !baselineLoading && !baselineStatus) {
      handleFetchBaselineStatus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, resolvedRepo?.repo_path]);

  // Update activeRepo when baselineStatus indicates accepted/approved baseline
  useEffect(() => {
    if (baselineStatus && resolvedRepo && repoUrlTrimmed) {
      // Check if baseline is accepted/approved
      const status = baselineStatus.status || baselineStatus.baseline_status;
      const isAccepted = status === "accepted" || status === "approved";
      const hash = baselineStatus.baseline_hash_sha256 || baselineStatus.baseline_hash;
      
      if (isAccepted && hash) {
        persistActiveRepo(repoUrlTrimmed, resolvedRepo, hash);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baselineStatus, resolvedRepo, repoUrlTrimmed]);

  // Generate baseline handler
  async function handleGenerateBaseline() {
    if (!resolvedRepo?.repo_path) {
      return;
    }
    setGenerateLoading(true);
    setGenerateError(null);
    setGenerateResult(null);
    setStatusRefreshed(false);
    try {
      const result = await generateBaseline({ 
        repoPath: resolvedRepo.repo_path,
        configDir: appliedConfigDir,
      });
      setGenerateResult(result);
      // Refresh baseline status after successful generation
      try {
        await handleFetchBaselineStatus();
        setStatusRefreshed(true);
      } catch (err) {
        // Status refresh failure doesn't block success display
      }
    } catch (err) {
      setGenerateError(err.message);
    } finally {
      setGenerateLoading(false);
    }
  }

  // Approve baseline handler
  async function handleApproveBaseline() {
    if (!resolvedRepo?.repo_path) {
      return;
    }
    setApproveLoading(true);
    setApproveError(null);
    setApproveResult(null);
    setApproveStatusRefreshed(false);
    try {
      const result = await approveBaseline({
        repoPath: resolvedRepo.repo_path,
        approvedBy,
        approvalNote,
      });
      setApproveResult(result);
      // Extract baseline hash from approveResult
      const hash = result?.baseline_hash_sha256 || null;
      if (hash) {
        persistActiveRepo(repoUrlTrimmed, resolvedRepo, hash);
      }
      // Refresh baseline status after successful approval
      try {
        await handleFetchBaselineStatus();
        setApproveStatusRefreshed(true);
        // The useEffect hook will handle updating activeRepo when baselineStatus changes
      } catch (err) {
        // Status refresh failure doesn't block success display
      }
    } catch (err) {
      setApproveError(err.message);
      setApproveResult(null);
    } finally {
      setApproveLoading(false);
    }
  }

  // Suggest module map handler
  async function handleSuggestModuleMap() {
    if (!resolvedRepo?.repo_path) {
      return;
    }
    setSuggestLoading(true);
    setSuggestError(null);
    setSuggestResult(null);
    try {
      const result = await suggestModuleMap({
        repoPath: resolvedRepo.repo_path,
        maxModules: suggestMaxModules,
      });
      setSuggestResult(result);
    } catch (err) {
      setSuggestError(err.message);
      setSuggestResult(null);
    } finally {
      setSuggestLoading(false);
    }
  }

  // Download module map handler
  function handleDownloadModuleMap() {
    if (!suggestResult?.module_map_suggestion) {
      return;
    }
    try {
      const jsonContent = JSON.stringify(suggestResult.module_map_suggestion, null, 2);
      const blob = new Blob([jsonContent], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "module_map.suggested.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      // Revoke URL after a short delay to ensure download starts
      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 0);
    } catch (err) {
      console.error("Failed to download module map:", err);
    }
  }

  // Apply module map handler
  async function handleApplyModuleMap() {
    if (!resolvedRepo?.repo_path || !suggestResult?.module_map_suggestion) {
      return;
    }
    setApplyLoading(true);
    setApplyError(null);
    setApplyResult(null);
    try {
      const result = await applyModuleMap({
        repoPath: resolvedRepo.repo_path,
        moduleMap: suggestResult.module_map_suggestion,
        configLabel: applyConfigLabel,
      });
      setApplyResult(result);
      setAppliedConfigDir(result.config_dir);
      // Save to localStorage
      try {
        localStorage.setItem("archdrift.onboarding.configDir", result.config_dir);
      } catch (error) {
        // Fail silently if localStorage is unavailable
      }
    } catch (err) {
      setApplyError(err.message);
      setApplyResult(null);
    } finally {
      setApplyLoading(false);
    }
  }

  // Run local analysis handler
  async function handleRunLocalAnalysis() {
    if (!resolvedRepo?.repo_path) {
      return;
    }
    setLocalAnalysisLoading(true);
    setLocalAnalysisError(null);
    setLocalAnalysisResult(null);
    try {
      // Determine configDir for conformance mode: appliedConfigDir takes priority, then effectiveConfigDir
      let configDirForAnalysis = undefined;
      if (localAnalysisMode === "conformance") {
        if (appliedConfigDir && appliedConfigDir.trim()) {
          configDirForAnalysis = appliedConfigDir;
        } else if (effectiveConfigDir && effectiveConfigDir.trim()) {
          configDirForAnalysis = effectiveConfigDir;
        }
      }
      const result = await analyzeLocalRepo({
        repoPath: resolvedRepo.repo_path,
        classifierMode: localAnalysisMode,
        maxCommits: localAnalysisMaxCommits,
        maxDrifts: localAnalysisMaxDrifts,
        configDir: configDirForAnalysis,
      });
      setLocalAnalysisResult(result);
      setLastLocalAnalysisMode(localAnalysisMode);
    } catch (err) {
      setLocalAnalysisError(err.message);
      setLocalAnalysisResult(null);
    } finally {
      setLocalAnalysisLoading(false);
    }
  }

  // Create snapshot handler
  async function handleCreateSnapshot() {
    if (!resolvedRepo?.repo_path || !appliedConfigDir) {
      return;
    }
    setSnapshotLoading(true);
    setSnapshotError(null);
    setSnapshotResult(null);
    try {
      const result = await createArchitectureSnapshot({
        repoPath: resolvedRepo.repo_path,
        configDir: appliedConfigDir,
        snapshotLabel,
        createdBy: snapshotCreatedBy,
        note: snapshotNote,
      });
      setSnapshotResult(result);
      // Store snapshot_id in localStorage
      try {
        if (result.snapshot_id) {
          localStorage.setItem("archdrift.onboarding.snapshotId", result.snapshot_id);
        }
      } catch (error) {
        // Fail silently if localStorage is unavailable
      }
    } catch (err) {
      setSnapshotError(err.message);
      setSnapshotResult(null);
    } finally {
      setSnapshotLoading(false);
    }
  }

  // Load snapshots handler
  async function handleLoadSnapshots() {
    if (!resolvedRepo?.repo_path) {
      return;
    }
    setSnapshotsLoading(true);
    setSnapshotsError(null);
    try {
      const result = await listArchitectureSnapshots({ 
        repoPath: resolvedRepo.repo_path, 
        limit: 20 
      });
      setSnapshotsList(result.snapshots || []);
    } catch (err) {
      setSnapshotsError(err.message);
      setSnapshotsList(null);
    } finally {
      setSnapshotsLoading(false);
    }
  }

  // Snapshot selection handler
  function handleSnapshotSelect(event) {
    const value = event.target.value;
    setSelectedSnapshotId(value || null);
    try {
      if (value && value.trim()) {
        localStorage.setItem("archdrift.onboarding.snapshotId", value.trim());
      } else {
        localStorage.removeItem("archdrift.onboarding.snapshotId");
      }
    } catch (error) {
      // Fail silently if localStorage is unavailable
    }
  }

  // Resolve effective config handler
  async function handleResolveEffectiveConfig() {
    if (!resolvedRepo?.repo_path || !selectedSnapshotId) {
      return;
    }
    setEffectiveError(null);
    setEffectiveResult(null);
    setEffectiveLoading(true);
    try {
      const result = await getEffectiveConfig({
        repoPath: resolvedRepo.repo_path,
        snapshotId: selectedSnapshotId,
      });
      setEffectiveResult(result);
      setEffectiveConfigDir(result.config_dir || null);
    } catch (err) {
      setEffectiveError(err.message);
      setEffectiveResult(null);
    } finally {
      setEffectiveLoading(false);
    }
  }

  // Validation for approvedBy
  const approvedByTrimmed = approvedBy.trim();
  const isApprovedByValid = approvedByTrimmed.length > 0;
  const showApprovedByError = approvedByTouched && !isApprovedByValid;

  // Next button disabled logic
  const isNextDisabled = 
    isLastStep || 
    (currentStep === 0 && !isValid) || 
    (currentStep === 1 && (!resolvedRepo?.repo_path || resolveLoading)) ||
    (currentStep === 2 && baselineLoading) ||
    (currentStep === 3 && generateLoading) ||
    (currentStep === 4 && approveLoading);

  return (
    <div className="flex flex-col">
      <div className="mb-4">
        <p className="text-sm text-slate-400 mb-2" data-testid="wizard-step-counter">
          Step {currentStep + 1} of {steps.length}
        </p>
        <h3 className="text-lg font-semibold text-slate-100" data-testid="wizard-step-title">
          {currentStepTitle}
        </h3>
      </div>
      <div className="mb-6">
        {currentStep === 0 ? (
          <div className="flex flex-col gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Repo URL or Local Path
              </label>
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => {
                  setRepoUrl(e.target.value);
                  setTouched(true);
                }}
                onBlur={() => setTouched(true)}
                data-testid="repo-url-input"
                className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                placeholder="https://github.com/org/repo or C:\\path\\to\\repo"
              />
            </div>
            <p className="text-xs text-slate-400" data-testid="repo-url-help">
              Example: https://github.com/org/repo OR C:\\path\\to\\repo
            </p>
            {showError && (
              <p className="text-sm text-rose-400" data-testid="repo-url-error">
                Repo URL or local path is required.
              </p>
            )}
          </div>
        ) : currentStep === 1 ? (
          <div className="flex flex-col gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Repo Input
              </label>
              <p className="text-sm text-slate-200 bg-slate-950 border border-slate-700 rounded-md px-3 py-2">
                {repoUrlTrimmed || "(empty)"}
              </p>
            </div>
            <button
              data-testid="resolve-repo-button"
              onClick={handleResolveRepo}
              disabled={resolveLoading}
              className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
            >
              Resolve Repo
            </button>
            {resolveLoading && (
              <p className="text-sm text-slate-400" data-testid="resolve-repo-loading">
                Resolving...
              </p>
            )}
            {resolvedRepo && (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-slate-200">
                  Resolved Path: <span className="text-slate-100 font-mono" data-testid="resolved-repo-path">{resolvedRepo.repo_path}</span>
                </p>
                <p className="text-sm text-slate-200">
                  Repo Name: <span className="text-slate-100 font-mono" data-testid="resolved-repo-name">{resolvedRepo.repo_name}</span>
                </p>
              </div>
            )}
            {resolveError && (
              <div
                role="alert"
                data-testid="resolve-repo-error"
                className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
              >
                Resolve failed: {resolveError}
              </div>
            )}
          </div>
        ) : currentStep === 2 ? (
          <div className="flex flex-col gap-3">
            {!resolvedRepo?.repo_path ? (
              <p className="text-sm text-slate-400">Repo not resolved yet.</p>
            ) : (
              <>
                <div className="mb-6 pt-6 border-t border-slate-700">
                  <div className="flex items-center justify-between mb-3">
                    <h5 className="text-sm font-semibold text-slate-200">
                      No Intended Architecture? (Guided Path)
                    </h5>
                    <button
                      data-testid="guided-path-toggle"
                      onClick={() => setGuidedPathExpanded(!guidedPathExpanded)}
                      className="text-sm text-emerald-400 hover:text-emerald-300"
                    >
                      {guidedPathExpanded ? "Hide Guided Path" : "Show Guided Path"}
                    </button>
                  </div>
                  {!guidedPathExpanded ? (
                    <p className="text-sm text-slate-400" data-testid="guided-path-summary">
                      Use this checklist to bootstrap an intended architecture for legacy repos.
                    </p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <ol className="list-decimal list-inside flex flex-col gap-2 text-sm">
                        <li data-testid="guided-step-1" className="flex items-center gap-2">
                          <span>1) Resolve Repo</span>
                          <span
                            data-testid="guided-step-1-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              resolvedRepo && resolvedRepo.repo_path && resolvedRepo.repo_path.trim()
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {resolvedRepo && resolvedRepo.repo_path && resolvedRepo.repo_path.trim() ? "DONE" : "TODO"}
                          </span>
                        </li>
                        <li data-testid="guided-step-2" className="flex items-center gap-2">
                          <span>2) Suggest Module Map</span>
                          <span
                            data-testid="guided-step-2-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              suggestResult && suggestResult.module_map_suggestion
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {suggestResult && suggestResult.module_map_suggestion ? "DONE" : "TODO"}
                          </span>
                        </li>
                        <li data-testid="guided-step-3" className="flex items-center gap-2">
                          <span>3) Apply Module Map</span>
                          <span
                            data-testid="guided-step-3-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              (appliedConfigDir && appliedConfigDir.trim()) || (applyResult && applyResult.config_dir)
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {(appliedConfigDir && appliedConfigDir.trim()) || (applyResult && applyResult.config_dir) ? "DONE" : "TODO"}
                          </span>
                        </li>
                        <li data-testid="guided-step-4" className="flex items-center gap-2">
                          <span>4) Create Snapshot</span>
                          <span
                            data-testid="guided-step-4-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              snapshotResult && snapshotResult.snapshot_id
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {snapshotResult && snapshotResult.snapshot_id ? "DONE" : "TODO"}
                          </span>
                        </li>
                        <li data-testid="guided-step-5" className="flex items-center gap-2">
                          <span>5) Select Snapshot</span>
                          <span
                            data-testid="guided-step-5-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              selectedSnapshotId && selectedSnapshotId.trim()
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {selectedSnapshotId && selectedSnapshotId.trim() ? "DONE" : "TODO"}
                          </span>
                        </li>
                        <li data-testid="guided-step-6" className="flex items-center gap-2">
                          <span>6) Resolve Effective Config</span>
                          <span
                            data-testid="guided-step-6-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              effectiveConfigDir && effectiveConfigDir.trim()
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {effectiveConfigDir && effectiveConfigDir.trim() ? "DONE" : "TODO"}
                          </span>
                        </li>
                        <li data-testid="guided-step-7" className="flex items-center gap-2">
                          <span>7) Run Conformance Analysis</span>
                          <span
                            data-testid="guided-step-7-status"
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              localAnalysisResult && Array.isArray(localAnalysisResult) && lastLocalAnalysisMode === "conformance"
                                ? "bg-emerald-900/30 text-emerald-300"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {localAnalysisResult && Array.isArray(localAnalysisResult) && lastLocalAnalysisMode === "conformance" ? "DONE" : "TODO"}
                          </span>
                        </li>
                      </ol>
                      <button
                        data-testid="guided-path-copy"
                        onClick={async () => {
                          setGuidedPathCopied(false);
                          setGuidedPathCopyError(null);
                          try {
                            const checklistText = [
                              `Resolve Repo: ${resolvedRepo && resolvedRepo.repo_path && resolvedRepo.repo_path.trim() ? "DONE" : "TODO"}`,
                              `Suggest Module Map: ${suggestResult && suggestResult.module_map_suggestion ? "DONE" : "TODO"}`,
                              `Apply Module Map: ${(appliedConfigDir && appliedConfigDir.trim()) || (applyResult && applyResult.config_dir) ? "DONE" : "TODO"}`,
                              `Create Snapshot: ${snapshotResult && snapshotResult.snapshot_id ? "DONE" : "TODO"}`,
                              `Select Snapshot: ${selectedSnapshotId && selectedSnapshotId.trim() ? "DONE" : "TODO"}`,
                              `Resolve Effective Config: ${effectiveConfigDir && effectiveConfigDir.trim() ? "DONE" : "TODO"}`,
                              `Run Conformance Analysis: ${localAnalysisResult && Array.isArray(localAnalysisResult) && lastLocalAnalysisMode === "conformance" ? "DONE" : "TODO"}`,
                            ].join("\n");
                            
                            if (navigator.clipboard && navigator.clipboard.writeText) {
                              await navigator.clipboard.writeText(checklistText);
                            } else {
                              // Fallback for older browsers
                              const textarea = document.createElement("textarea");
                              textarea.value = checklistText;
                              textarea.style.position = "fixed";
                              textarea.style.opacity = "0";
                              document.body.appendChild(textarea);
                              textarea.select();
                              document.execCommand("copy");
                              document.body.removeChild(textarea);
                            }
                            setGuidedPathCopied(true);
                            setTimeout(() => setGuidedPathCopied(false), 2000);
                          } catch (err) {
                            setGuidedPathCopyError(err.message);
                          }
                        }}
                        className="inline-flex items-center justify-center rounded-md bg-slate-700 hover:bg-slate-600 px-4 py-2 text-sm font-medium text-white"
                      >
                        Copy Checklist
                      </button>
                      {guidedPathCopied && (
                        <p className="text-sm text-emerald-400" data-testid="guided-path-copied">
                          Copied.
                        </p>
                      )}
                      {guidedPathCopyError && (
                        <div
                          role="alert"
                          data-testid="guided-path-copy-error"
                          className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                        >
                          Copy failed: {guidedPathCopyError}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <button
                  data-testid="baseline-status-refresh"
                  onClick={handleFetchBaselineStatus}
                  disabled={baselineLoading || !resolvedRepo?.repo_path}
                  className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                >
                  Refresh Status
                </button>
                {baselineLoading && (
                  <p className="text-sm text-slate-400" data-testid="baseline-status-loading">
                    Loading baseline status...
                  </p>
                )}
                {baselineError && (
                  <div
                    role="alert"
                    data-testid="baseline-status-error"
                    className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                  >
                    Status fetch failed: {baselineError}
                  </div>
                )}
                {baselineStatus && (
                  <div className="flex flex-col gap-3">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline State
                      </label>
                      <p className="text-sm text-slate-200" data-testid="baseline-status-state">
                        {baselineStatus.baseline_status || baselineStatus.status || "(unknown)"}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline Hash
                      </label>
                      <p className="text-sm text-slate-200 font-mono" data-testid="baseline-status-hash">
                        {baselineStatus.baseline_hash_sha256 || baselineStatus.baseline_hash || ""}
                      </p>
                    </div>
                    {baselineStatus.baseline_health && (
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Baseline Health
                        </label>
                        <div className="flex flex-col gap-2 text-sm">
                          <p>
                            baseline_ready: <span className="text-slate-200" data-testid="baseline-health-baseline-ready">{String(baselineStatus.baseline_health.baseline_ready ?? "unknown")}</span>
                          </p>
                          <p>
                            mapping_ready: <span className="text-slate-200" data-testid="baseline-health-mapping-ready">{String(baselineStatus.baseline_health.mapping_ready ?? "unknown")}</span>
                          </p>
                          {Array.isArray(baselineStatus.baseline_health.next_actions) && baselineStatus.baseline_health.next_actions.length > 0 && (
                            <div data-testid="baseline-health-next-actions">
                              <p className="text-slate-300 mb-1">next_actions:</p>
                              <ul className="list-disc list-inside text-slate-200 ml-2">
                                {baselineStatus.baseline_health.next_actions.map((action, idx) => (
                                  <li key={idx}>{action}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-6 pt-6 border-t border-slate-700">
                  <h4 className="text-sm font-semibold text-slate-200 mb-3">
                    Run Local Analysis (Legacy)
                  </h4>
                  {!resolvedRepo?.repo_path ? (
                    <p className="text-sm text-slate-400">Repo not resolved yet.</p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Classifier Mode
                        </label>
                        <select
                          value={localAnalysisMode}
                          onChange={(e) => setLocalAnalysisMode(e.target.value)}
                          data-testid="local-analysis-mode"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                        >
                          <option value="keywords">keywords</option>
                          <option value="conformance">conformance</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Max Commits
                        </label>
                        <input
                          type="number"
                          value={localAnalysisMaxCommits}
                          onChange={(e) => {
                            const value = parseInt(e.target.value, 10);
                            if (!isNaN(value)) {
                              const clamped = Math.max(1, Math.min(500, value));
                              setLocalAnalysisMaxCommits(clamped);
                            }
                          }}
                          min={1}
                          max={500}
                          data-testid="local-analysis-max-commits"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Max Drifts
                        </label>
                        <input
                          type="number"
                          value={localAnalysisMaxDrifts}
                          onChange={(e) => {
                            const value = parseInt(e.target.value, 10);
                            if (!isNaN(value)) {
                              const clamped = Math.max(1, Math.min(50, value));
                              setLocalAnalysisMaxDrifts(clamped);
                            }
                          }}
                          min={1}
                          max={50}
                          data-testid="local-analysis-max-drifts"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                        />
                      </div>
                      {localAnalysisMode === "conformance" && !appliedConfigDir && !effectiveConfigDir && (
                        <p className="text-sm text-slate-400" data-testid="local-analysis-conformance-note">
                          Apply module map first OR resolve effective config from a snapshot to enable conformance.
                        </p>
                      )}
                      <button
                        data-testid="run-local-analysis-button"
                        onClick={handleRunLocalAnalysis}
                        disabled={
                          localAnalysisLoading ||
                          !resolvedRepo?.repo_path ||
                          (localAnalysisMode === "conformance" && !appliedConfigDir && !effectiveConfigDir)
                        }
                        className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                      >
                        Run Local Analysis
                      </button>
                      {localAnalysisLoading && (
                        <p className="text-sm text-slate-400" data-testid="run-local-analysis-loading">
                          Running analysis...
                        </p>
                      )}
                      {localAnalysisError && (
                        <div
                          role="alert"
                          data-testid="run-local-analysis-error"
                          className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                        >
                          Analysis failed: {localAnalysisError}
                        </div>
                      )}
                      {localAnalysisResult && (
                        <div className="flex flex-col gap-2">
                          <p className="text-sm text-slate-200" data-testid="run-local-analysis-success">
                            Analysis complete: {localAnalysisResult.length} drifts
                          </p>
                          <p className="text-xs text-slate-400" data-testid="run-local-analysis-hint">
                            Close the wizard and open the timeline to view latest drifts.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="mt-6 pt-6 border-t border-slate-700">
                  <h4 className="text-sm font-semibold text-slate-200 mb-3">
                    Architecture Snapshot (Legacy)
                  </h4>
                  {!resolvedRepo?.repo_path ? (
                    <p className="text-sm text-slate-400">Repo not resolved yet.</p>
                  ) : !appliedConfigDir ? (
                    <div className="flex flex-col gap-3">
                      <p className="text-sm text-slate-400">Apply module map first to create a snapshot.</p>
                      <button
                        data-testid="create-snapshot-button"
                        disabled={true}
                        className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                      >
                        Create Snapshot
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Snapshot Label
                        </label>
                        <input
                          type="text"
                          value={snapshotLabel}
                          onChange={(e) => setSnapshotLabel(e.target.value)}
                          data-testid="snapshot-label"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                          placeholder="v1"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Created By
                        </label>
                        <input
                          type="text"
                          value={snapshotCreatedBy}
                          onChange={(e) => setSnapshotCreatedBy(e.target.value)}
                          data-testid="snapshot-created-by"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                          placeholder="Optional"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Note
                        </label>
                        <input
                          type="text"
                          value={snapshotNote}
                          onChange={(e) => setSnapshotNote(e.target.value)}
                          data-testid="snapshot-note"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                          placeholder="Optional"
                        />
                      </div>
                      <button
                        data-testid="create-snapshot-button"
                        onClick={handleCreateSnapshot}
                        disabled={snapshotLoading || !resolvedRepo?.repo_path || !appliedConfigDir}
                        className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                      >
                        Create Snapshot
                      </button>
                      {snapshotLoading && (
                        <p className="text-sm text-slate-400" data-testid="create-snapshot-loading">
                          Creating snapshot...
                        </p>
                      )}
                      {snapshotError && (
                        <div
                          role="alert"
                          data-testid="create-snapshot-error"
                          className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                        >
                          Snapshot failed: {snapshotError}
                        </div>
                      )}
                      {snapshotResult && (
                        <div className="flex flex-col gap-2">
                          <p className="text-sm text-slate-200" data-testid="snapshot-id">
                            Snapshot ID: {snapshotResult.snapshot_id || ""}
                          </p>
                          <p className="text-sm text-slate-200" data-testid="snapshot-is-new">
                            Is New: {String(snapshotResult.is_new ?? false)}
                          </p>
                          <p className="text-sm text-slate-200" data-testid="snapshot-created-at">
                            Created At: {snapshotResult.created_at_utc || ""}
                          </p>
                          <p className="text-sm text-slate-200" data-testid="snapshot-module-map-sha">
                            Module Map SHA256: {snapshotResult.module_map_sha256 || ""}
                          </p>
                          {snapshotResult.snapshot_dir && (
                            <p className="text-sm text-slate-200" data-testid="snapshot-dir">
                              Snapshot Dir: {snapshotResult.snapshot_dir}
                            </p>
                          )}
                          <p className="text-xs text-slate-400" data-testid="snapshot-help">
                            Snapshots let teams version intended architecture over time.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                  <div className="mt-6 pt-6 border-t border-slate-700">
                    <h5 className="text-sm font-semibold text-slate-200 mb-3">
                      Select Snapshot
                    </h5>
                    {!resolvedRepo?.repo_path ? (
                      <p className="text-sm text-slate-400">Repo not resolved yet.</p>
                    ) : (
                      <div className="flex flex-col gap-3">
                        <button
                          data-testid="load-snapshots-button"
                          onClick={handleLoadSnapshots}
                          disabled={snapshotsLoading || !resolvedRepo?.repo_path}
                          className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                        >
                          Load Snapshots
                        </button>
                        {snapshotsLoading && (
                          <p className="text-sm text-slate-400" data-testid="load-snapshots-loading">
                            Loading snapshots...
                          </p>
                        )}
                        {snapshotsError && (
                          <div
                            role="alert"
                            data-testid="load-snapshots-error"
                            className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                          >
                            Load failed: {snapshotsError}
                          </div>
                        )}
                        {snapshotsList !== null && (
                          <>
                            {snapshotsList.length === 0 ? (
                              <p className="text-sm text-slate-400" data-testid="no-snapshots">
                                No snapshots found.
                              </p>
                            ) : (
                              <>
                                <div>
                                  <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Active Snapshot
                                  </label>
                                  <select
                                    value={selectedSnapshotId || ""}
                                    onChange={handleSnapshotSelect}
                                    data-testid="snapshot-select"
                                    className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                                  >
                                    <option value="">(none)</option>
                                    {snapshotsList.map((snapshot) => (
                                      <option key={snapshot.snapshot_id} value={snapshot.snapshot_id}>
                                        {snapshot.snapshot_label || snapshot.snapshot_id} — {snapshot.created_at_utc || ""}
                                      </option>
                                    ))}
                                  </select>
                                </div>
                                {selectedSnapshotId && (
                                  <div className="flex flex-col gap-2" data-testid="snapshot-details">
                                    {(() => {
                                      const selected = snapshotsList.find(s => s.snapshot_id === selectedSnapshotId);
                                      if (!selected) return null;
                                      return (
                                        <>
                                          <div>
                                            <label className="block text-sm font-medium text-slate-300 mb-1">
                                              Snapshot ID
                                            </label>
                                            <p className="text-sm text-slate-200 font-mono">
                                              {selected.snapshot_id || ""}
                                            </p>
                                          </div>
                                          <div>
                                            <label className="block text-sm font-medium text-slate-300 mb-1">
                                              Label
                                            </label>
                                            <p className="text-sm text-slate-200">
                                              {selected.snapshot_label || "(none)"}
                                            </p>
                                          </div>
                                          <div>
                                            <label className="block text-sm font-medium text-slate-300 mb-1">
                                              Created At
                                            </label>
                                            <p className="text-sm text-slate-200">
                                              {selected.created_at_utc || ""}
                                            </p>
                                          </div>
                                          <div>
                                            <label className="block text-sm font-medium text-slate-300 mb-1">
                                              Created By
                                            </label>
                                            <p className="text-sm text-slate-200">
                                              {selected.created_by || "(none)"}
                                            </p>
                                          </div>
                                          <div>
                                            <label className="block text-sm font-medium text-slate-300 mb-1">
                                              Note
                                            </label>
                                            <p className="text-sm text-slate-200">
                                              {selected.note || "(none)"}
                                            </p>
                                          </div>
                                        </>
                                      );
                                    })()}
                                  </div>
                                )}
                              </>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="mt-6 pt-6 border-t border-slate-700">
                    <h5 className="text-sm font-semibold text-slate-200 mb-3">
                      Effective Config
                    </h5>
                    {!resolvedRepo?.repo_path ? (
                      <p className="text-sm text-slate-400">Repo not resolved yet.</p>
                    ) : (
                      <div className="flex flex-col gap-3">
                        {!selectedSnapshotId ? (
                          <p className="text-sm text-slate-400" data-testid="effective-config-note">
                            Select a snapshot to resolve config.
                          </p>
                        ) : null}
                        <button
                          data-testid="resolve-effective-config-button"
                          onClick={handleResolveEffectiveConfig}
                          disabled={effectiveLoading || !resolvedRepo?.repo_path || !selectedSnapshotId}
                          className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                        >
                          Resolve Effective Config
                        </button>
                        {effectiveLoading && (
                          <p className="text-sm text-slate-400" data-testid="resolve-effective-config-loading">
                            Resolving config...
                          </p>
                        )}
                        {effectiveError && (
                          <div
                            role="alert"
                            data-testid="resolve-effective-config-error"
                            className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                          >
                            Resolve failed: {effectiveError}
                          </div>
                        )}
                        {effectiveResult && (
                          <div className="flex flex-col gap-2">
                            <p className="text-sm text-slate-200" data-testid="effective-config-dir">
                              Config Dir: {effectiveResult.config_dir || ""}
                            </p>
                            <p className="text-sm text-slate-200" data-testid="effective-snapshot-id">
                              Snapshot ID: {effectiveResult.snapshot_id || ""}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-6 pt-6 border-t border-slate-700">
                  <h4 className="text-sm font-semibold text-slate-200 mb-3">
                    Module Map Suggestion (Legacy)
                  </h4>
                  {!resolvedRepo?.repo_path ? (
                    <p className="text-sm text-slate-400">Repo not resolved yet.</p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Max Modules
                        </label>
                        <input
                          type="number"
                          value={suggestMaxModules}
                          onChange={(e) => {
                            const value = parseInt(e.target.value, 10);
                            if (!isNaN(value)) {
                              const clamped = Math.max(2, Math.min(20, value));
                              setSuggestMaxModules(clamped);
                            }
                          }}
                          min={2}
                          max={20}
                          data-testid="suggest-module-max"
                          className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                        />
                      </div>
                      <button
                        data-testid="suggest-module-map-button"
                        onClick={handleSuggestModuleMap}
                        disabled={suggestLoading || !resolvedRepo?.repo_path}
                        className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                      >
                        Suggest Module Map
                      </button>
                      {suggestLoading && (
                        <p className="text-sm text-slate-400" data-testid="suggest-module-map-loading">
                          Suggesting module map...
                        </p>
                      )}
                      {suggestError && (
                        <div
                          role="alert"
                          data-testid="suggest-module-map-error"
                          className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                        >
                          Suggestion failed: {suggestError}
                        </div>
                      )}
                      {suggestResult && (
                        <div className="flex flex-col gap-3">
                          <div>
                            <p className="text-sm text-slate-200" data-testid="suggest-method">
                              Method: {suggestResult.suggestion_method}
                            </p>
                          </div>
                          {suggestResult.buckets && suggestResult.buckets.length > 0 && (
                            <div>
                              <label className="block text-sm font-medium text-slate-300 mb-1">
                                Buckets
                              </label>
                              <div className="text-sm text-slate-200" data-testid="suggest-buckets">
                                {suggestResult.buckets.map((bucketItem, idx) => (
                                  <p key={idx}>
                                    {bucketItem.bucket} — {bucketItem.file_count} files
                                  </p>
                                ))}
                              </div>
                            </div>
                          )}
                          {suggestResult.module_map_suggestion?.modules && (
                            <div>
                              <label className="block text-sm font-medium text-slate-300 mb-1">
                                Modules
                              </label>
                              <div className="text-sm text-slate-200" data-testid="suggest-modules">
                                {suggestResult.module_map_suggestion.modules.map((module, idx) => (
                                  <p key={idx}>
                                    {module.id}: {module.roots.join(", ")}
                                  </p>
                                ))}
                              </div>
                            </div>
                          )}
                          {suggestResult.notes && suggestResult.notes.length > 0 && (
                            <div>
                              <label className="block text-sm font-medium text-slate-300 mb-1">
                                Notes
                              </label>
                              <div className="text-sm text-slate-200" data-testid="suggest-notes">
                                {suggestResult.notes.map((note, idx) => (
                                  <p key={idx}>{note}</p>
                                ))}
                              </div>
                            </div>
                          )}
                          <button
                            data-testid="suggest-download"
                            onClick={handleDownloadModuleMap}
                            className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-medium text-white"
                          >
                            Download module_map.json
                          </button>
                        </div>
                      )}
                      {suggestResult && (
                        <div className="mt-4 pt-4 border-t border-slate-700">
                          <h5 className="text-sm font-medium text-slate-300 mb-3">
                            Apply Module Map
                          </h5>
                          <div className="flex flex-col gap-3">
                            <div>
                              <label className="block text-sm font-medium text-slate-300 mb-2">
                                Config Label
                              </label>
                              <input
                                type="text"
                                value={applyConfigLabel}
                                onChange={(e) => setApplyConfigLabel(e.target.value)}
                                data-testid="apply-config-label"
                                className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                                placeholder="suggested"
                              />
                            </div>
                            <button
                              data-testid="apply-module-map-button"
                              onClick={handleApplyModuleMap}
                              disabled={applyLoading || !resolvedRepo?.repo_path || !suggestResult?.module_map_suggestion}
                              className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                            >
                              Apply Module Map
                            </button>
                            {applyLoading && (
                              <p className="text-sm text-slate-400" data-testid="apply-module-map-loading">
                                Applying module map...
                              </p>
                            )}
                            {applyError && (
                              <div
                                role="alert"
                                data-testid="apply-module-map-error"
                                className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                              >
                                Apply failed: {applyError}
                              </div>
                            )}
                            {applyResult && (
                              <div className="flex flex-col gap-2">
                                <p className="text-sm text-slate-200" data-testid="applied-config-dir">
                                  Config Dir: {applyResult.config_dir}
                                </p>
                                <p className="text-sm text-slate-200" data-testid="applied-module-map-sha">
                                  Module Map SHA256: {applyResult.module_map_sha256}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        ) : currentStep === 3 ? (
          <div className="flex flex-col gap-3">
            {!resolvedRepo?.repo_path ? (
              <p className="text-sm text-slate-400">Repo not resolved yet.</p>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Repo Path
                  </label>
                  <p className="text-sm text-slate-200 bg-slate-950 border border-slate-700 rounded-md px-3 py-2 font-mono">
                    {resolvedRepo.repo_path}
                  </p>
                </div>
                <button
                  data-testid="generate-baseline-button"
                  onClick={handleGenerateBaseline}
                  disabled={generateLoading || !resolvedRepo?.repo_path}
                  className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                >
                  Generate Baseline
                </button>
                {generateLoading && (
                  <p className="text-sm text-slate-400" data-testid="generate-baseline-loading">
                    Generating baseline...
                  </p>
                )}
                {generateError && (
                  <div
                    role="alert"
                    data-testid="generate-baseline-error"
                    className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                  >
                    Generate failed: {generateError}
                  </div>
                )}
                {generateResult && (
                  <div className="flex flex-col gap-2">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline Status
                      </label>
                      <p className="text-sm text-slate-200" data-testid="generate-baseline-status">
                        {generateResult.baseline_status || "(unknown)"}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline Hash
                      </label>
                      <p className="text-sm text-slate-200 font-mono" data-testid="generate-baseline-hash">
                        {generateResult.baseline_hash_sha256 || ""}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Edge Count
                      </label>
                      <p className="text-sm text-slate-200" data-testid="generate-baseline-edges">
                        {generateResult.edge_count || ""}
                      </p>
                    </div>
                    {statusRefreshed && (
                      <p className="text-xs text-slate-400" data-testid="generate-baseline-status-refreshed">
                        Status refreshed.
                      </p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        ) : currentStep === 4 ? (
          <div className="flex flex-col gap-3">
            {!resolvedRepo?.repo_path ? (
              <p className="text-sm text-slate-400">Repo not resolved yet.</p>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Repo Path
                  </label>
                  <p className="text-sm text-slate-200 bg-slate-950 border border-slate-700 rounded-md px-3 py-2 font-mono">
                    {resolvedRepo.repo_path}
                  </p>
                </div>
                {baselineStatus === null ? (
                  <div className="flex flex-col gap-2">
                    <p className="text-sm text-slate-400">Baseline status not loaded yet.</p>
                    <button
                      data-testid="approve-load-status-button"
                      onClick={handleFetchBaselineStatus}
                      disabled={baselineLoading || !resolvedRepo?.repo_path}
                      className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                    >
                      Load Status
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline Exists
                      </label>
                      <p className="text-sm text-slate-200" data-testid="approve-baseline-exists">
                        {String(baselineStatus.exists ?? "unknown")}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline Status
                      </label>
                      <p className="text-sm text-slate-200" data-testid="approve-baseline-status">
                        {baselineStatus.status ?? "(unknown)"}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Baseline Hash
                      </label>
                      <p className="text-sm text-slate-200 font-mono" data-testid="approve-baseline-hash">
                        {baselineStatus.baseline_hash_sha256 ?? ""}
                      </p>
                    </div>
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Approved By
                  </label>
                  <input
                    type="text"
                    value={approvedBy}
                    onChange={(e) => {
                      setApprovedBy(e.target.value);
                      setApprovedByTouched(true);
                    }}
                    onBlur={() => setApprovedByTouched(true)}
                    data-testid="approve-approved-by"
                    className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                    placeholder="Enter your name or email"
                  />
                  {showApprovedByError && (
                    <p className="text-sm text-rose-400 mt-1" data-testid="approve-approved-by-error">
                      Approved By is required.
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Approval Note (optional)
                  </label>
                  <textarea
                    value={approvalNote}
                    onChange={(e) => setApprovalNote(e.target.value)}
                    data-testid="approve-approval-note"
                    rows={3}
                    className="w-full rounded-md bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent resize-none"
                    placeholder="Optional note about this approval"
                  />
                </div>
                <button
                  data-testid="approve-baseline-button"
                  onClick={handleApproveBaseline}
                  disabled={
                    !resolvedRepo?.repo_path ||
                    !isApprovedByValid ||
                    approveLoading ||
                    baselineStatus?.exists === false ||
                    baselineStatus?.status === "missing"
                  }
                  className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
                >
                  Approve Baseline
                </button>
                {approveLoading && (
                  <p className="text-sm text-slate-400" data-testid="approve-baseline-loading">
                    Approving baseline...
                  </p>
                )}
                {approveError && (
                  <div
                    role="alert"
                    data-testid="approve-baseline-error"
                    className="text-sm text-rose-400 bg-rose-900/20 border border-rose-800 rounded-md px-3 py-2"
                  >
                    Approve failed: {approveError}
                  </div>
                )}
                {approveResult && (
                  <div className="flex flex-col gap-2">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Approved By
                      </label>
                      <p className="text-sm text-slate-200" data-testid="approve-result-approved-by">
                        {approveResult.approved_by ?? ""}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Approved At
                      </label>
                      <p className="text-sm text-slate-200" data-testid="approve-result-approved-at">
                        {approveResult.approved_at ?? ""}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">
                        Active Exceptions
                      </label>
                      <p className="text-sm text-slate-200" data-testid="approve-result-exceptions">
                        {approveResult.active_exceptions_count ?? 0}
                      </p>
                    </div>
                    {approveResult.status && (
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-1">
                          Status
                        </label>
                        <p className="text-sm text-slate-200">
                          {approveResult.status}
                        </p>
                      </div>
                    )}
                    {approveResult.baseline_hash_sha256 && (
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-1">
                          Baseline Hash
                        </label>
                        <p className="text-sm text-slate-200 font-mono">
                          {approveResult.baseline_hash_sha256}
                        </p>
                      </div>
                    )}
                    {approveStatusRefreshed && (
                      <p className="text-xs text-slate-400" data-testid="approve-status-refreshed">
                        Status refreshed.
                      </p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          <p className="text-slate-300">TODO: Implement in MT1.06</p>
        )}
      </div>
      <div className="flex gap-2 justify-end">
        <button
          data-testid="wizard-back"
          onClick={() => dispatch({ type: "PREV_STEP" })}
          disabled={isFirstStep || approveLoading}
          className="inline-flex items-center justify-center rounded-md bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
        >
          Back
        </button>
        <button
          data-testid="wizard-next"
          onClick={() => dispatch({ type: "NEXT_STEP" })}
          disabled={isNextDisabled}
          className="inline-flex items-center justify-center rounded-md bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 text-sm font-medium text-white"
        >
          Next
        </button>
        <button
          data-testid="wizard-close"
          onClick={onClose}
          className="inline-flex items-center justify-center rounded-md bg-slate-700 hover:bg-slate-600 px-4 py-2 text-sm font-medium text-white"
        >
          Close
        </button>
      </div>
    </div>
  );
}

export default OnboardingWizard;

