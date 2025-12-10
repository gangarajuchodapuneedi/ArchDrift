import axios from "axios";


const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:9000";
const api = axios.create({
  baseURL: "API_BASE_URL,",
  timeout: 300000, // 5 minute timeout to match backend
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
    });
    return Promise.reject(error);
  }
);

export async function fetchDrifts() {
  const res = await api.get("/drifts");
  const data = res.data;
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.items)) {
    return data.items;
  }
  return [];
}

export async function analyzeRepo({ repoUrl, maxCommits = 50, maxDrifts = 5 }) {
  const payload = {
    repo_url: repoUrl,
    max_commits: maxCommits,
    max_drifts: maxDrifts,
  };
  const res = await api.post("/analyze-repo", payload);
  return res.data ?? [];
}

