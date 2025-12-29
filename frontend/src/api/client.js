import axios from "axios";

// Automatically detect backend URL based on current hostname
// If accessed via network IP (not localhost), use the same host for backend
function getBackendUrl() {
  // Check if environment variable is set
  if (import.meta.env.VITE_BACKEND_URL) {
    return import.meta.env.VITE_BACKEND_URL;
  }
  
  // Get current hostname
  const hostname = window.location.hostname;
  
  // If accessing via localhost or 127.0.0.1, use localhost for backend
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://localhost:8000";
  }
  
  // If accessing via network IP, use the same hostname with port 8000
  // This handles cases like http://192.168.1.100:5173 -> http://192.168.1.100:8000
  return `http://${hostname}:8000`;
}

const API_BASE_URL = getBackendUrl();
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 330000, // 5.5 minute timeout (backend has 300s timeout, add buffer)
});

// Add response interceptor to log errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error("API Error:", {
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      message: error.message,
      code: error.code,
      request: error.request ? "Request made but no response" : "No request made",
    });
    return Promise.reject(error);
  }
);

/**
 * Fetch all drifts from the backend.
 * 
 * Handles multiple response shapes for robustness:
 * - Array: [{...}, {...}] (legacy/direct)
 * - Wrapper with 'items': {items: [{...}, {...}]} (current backend format)
 * - Wrapper with 'drifts': {drifts: [{...}, {...}]} (alternative format)
 * 
 * Always returns a normalized array of drifts for consistent usage throughout the app.
 * 
 * @returns {Promise<Array>} Array of drift objects
 */
export async function fetchDrifts() {
  const res = await api.get("/drifts");
  const data = res.data;
  // Accept both array and wrapper shapes for robustness
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  if (data && Array.isArray(data.drifts)) {
    return data.drifts;
  }
  return [];
}

export async function analyzeRepo({ repoUrl, maxCommits = 50, maxDrifts = 5, classifierMode }) {
  const payload = {
    repo_url: repoUrl,
    max_commits: maxCommits,
    max_drifts: maxDrifts,
  };
  if (classifierMode) {
    payload.classifier_mode = classifierMode;
  }
  const res = await api.post("/analyze-repo", payload);
  return res.data ?? [];
}

export async function fetchBaselineStatus(repoPath, configDir) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  const params = { repo_path: repoPathTrimmed };
  const configDirTrimmed = configDir?.trim();
  if (configDirTrimmed) {
    params.config_dir = configDirTrimmed;
  }
  
  try {
    const res = await api.get("/baseline/status", { params });
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    const message = detail || (status ? `HTTP ${status}` : "Failed to fetch baseline status");
    throw new Error(message);
  }
}

export async function resolveRepo(repoUrl) {
  if (!repoUrl || !repoUrl.trim()) {
    throw new Error("repoUrl is required");
  }
  
  try {
    const res = await api.post("/onboarding/resolve-repo", { repo_url: repoUrl });
    return res.data;
  } catch (error) {
    // Handle HTTP 408 (timeout from backend)
    if (error.response?.status === 408) {
      throw new Error("Repository resolution timed out after 2 minutes. The repository may be too large or there may be network issues.");
    }
    // Handle network errors
    if (error.code === "ECONNREFUSED" || error.code === "ERR_NETWORK" || error.message?.includes("Network Error")) {
      throw new Error("Cannot connect to backend server. Please ensure the backend is running on port 8000.");
    }
    if (error.code === "ETIMEDOUT" || error.message?.includes("timeout")) {
      throw new Error("Request timed out. The repository resolution may be taking too long.");
    }
    // Handle HTTP errors
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    const message = detail || (status ? `HTTP ${status}` : "Failed to resolve repository");
    throw new Error(message);
  }
}

export async function generateBaseline({ repoPath, configDir, maxFiles, maxFileBytes }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  const payload = { repo_path: repoPathTrimmed };
  const configDirTrimmed = configDir?.trim();
  if (configDirTrimmed) {
    payload.config_dir = configDirTrimmed;
  }
  if (typeof maxFiles === "number") {
    payload.max_files = maxFiles;
  }
  if (typeof maxFileBytes === "number") {
    payload.max_file_bytes = maxFileBytes;
  }
  
  try {
    const res = await api.post("/baseline/generate", payload);
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const message = detail || "Failed to generate baseline";
    throw new Error(message);
  }
}

export async function approveBaseline({ repoPath, approvedBy, approvalNote }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  const approvedByTrimmed = approvedBy?.trim();
  if (!approvedByTrimmed) {
    throw new Error("approvedBy is required");
  }
  
  const payload = {
    repo_path: repoPathTrimmed,
    approved_by: approvedByTrimmed,
  };
  const approvalNoteTrimmed = approvalNote?.trim();
  if (approvalNoteTrimmed) {
    payload.approval_note = approvalNoteTrimmed;
  }
  
  try {
    const res = await api.post("/baseline/approve", payload);
    return res.data ?? null;
  } catch (error) {
    const detail = error.response?.data?.detail;
    throw new Error(detail || "Failed to approve baseline");
  }
}

export async function suggestModuleMap({ repoPath, maxModules }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  const payload = {
    repo_path: repoPathTrimmed,
  };
  if (typeof maxModules === "number") {
    payload.max_modules = maxModules;
  }
  
  try {
    const res = await api.post("/onboarding/suggest-module-map", payload);
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    const message = detail || (status ? `HTTP ${status}` : "Failed to suggest module map");
    throw new Error(message);
  }
}

export async function applyModuleMap({ repoPath, moduleMap, configLabel }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  if (!moduleMap || typeof moduleMap !== "object" || Array.isArray(moduleMap)) {
    throw new Error("moduleMap is required");
  }
  
  const payload = {
    repo_path: repoPathTrimmed,
    module_map: moduleMap,
  };
  const configLabelTrimmed = configLabel?.trim();
  if (configLabelTrimmed) {
    payload.config_label = configLabelTrimmed;
  }
  
  try {
    const res = await api.post("/onboarding/apply-module-map", payload);
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    const message = detail || (status ? `HTTP ${status}` : "Failed to apply module map");
    throw new Error(message);
  }
}

export async function analyzeLocalRepo({ repoPath, configDir, classifierMode, maxCommits, maxDrifts }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  if (classifierMode !== undefined && classifierMode !== null) {
    if (classifierMode !== "keywords" && classifierMode !== "conformance") {
      throw new Error("classifierMode must be 'keywords' or 'conformance'");
    }
  }
  
  const payload = {
    repo_path: repoPathTrimmed,
    max_commits: typeof maxCommits === "number" ? maxCommits : 50,
    max_drifts: typeof maxDrifts === "number" ? maxDrifts : 5,
  };
  
  const configDirTrimmed = configDir?.trim();
  if (configDirTrimmed) {
    payload.config_dir = configDirTrimmed;
  }
  
  if (classifierMode !== undefined && classifierMode !== null) {
    payload.classifier_mode = classifierMode;
  }
  
  try {
    const res = await api.post("/analyze-local", payload);
    return res.data ?? [];
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    // Log the full error for debugging
    console.error("analyzeLocalRepo error:", {
      status,
      detail,
      url: error.config?.url,
      baseURL: error.config?.baseURL,
      payload,
    });
    if (detail) {
      throw new Error(detail);
    }
    throw new Error(status ? `HTTP ${status}` : "Failed to analyze local repo");
  }
}

export async function createArchitectureSnapshot({ repoPath, configDir, snapshotLabel, createdBy, note }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  const configDirTrimmed = configDir?.trim();
  if (!configDirTrimmed) {
    throw new Error("configDir is required");
  }
  
  const payload = {
    repo_path: repoPathTrimmed,
    config_dir: configDirTrimmed,
  };
  
  const snapshotLabelTrimmed = snapshotLabel?.trim();
  if (snapshotLabelTrimmed) {
    payload.snapshot_label = snapshotLabelTrimmed;
  }
  
  const createdByTrimmed = createdBy?.trim();
  if (createdByTrimmed) {
    payload.created_by = createdByTrimmed;
  }
  
  const noteTrimmed = note?.trim();
  if (noteTrimmed) {
    payload.note = noteTrimmed;
  }
  
  try {
    const res = await api.post("/onboarding/architecture-snapshot/create", payload);
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    // Log the full error for debugging
    console.error("createArchitectureSnapshot error:", {
      status,
      detail,
      url: error.config?.url,
      baseURL: error.config?.baseURL,
      payload,
    });
    if (detail) {
      throw new Error(detail);
    }
    throw new Error(status ? `HTTP ${status}` : "Failed to create architecture snapshot");
  }
}

export async function listArchitectureSnapshots({ repoPath, limit }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  let limitValue = limit !== undefined ? limit : 20;
  limitValue = Math.max(1, Math.min(100, limitValue));
  
  const params = {
    repo_path: repoPathTrimmed,
    limit: limitValue,
  };
  
  try {
    const res = await api.get("/onboarding/architecture-snapshot/list", { params });
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    if (detail) {
      throw new Error(detail);
    }
    throw new Error(status ? `HTTP ${status}` : "Failed to list architecture snapshots");
  }
}

export async function getEffectiveConfig({ repoPath, snapshotId }) {
  const repoPathTrimmed = repoPath?.trim();
  if (!repoPathTrimmed) {
    throw new Error("repoPath is required");
  }
  
  const params = {
    repo_path: repoPathTrimmed,
  };
  
  const snapshotIdTrimmed = snapshotId?.trim();
  if (snapshotIdTrimmed) {
    params.snapshot_id = snapshotIdTrimmed;
  }
  
  try {
    const res = await api.get("/onboarding/effective-config", { params });
    return res.data;
  } catch (error) {
    const detail = error.response?.data?.detail;
    const status = error.response?.status;
    if (detail) {
      throw new Error(detail);
    }
    throw new Error(status ? `HTTP ${status}` : "Failed to get effective config");
  }
}

