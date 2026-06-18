const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Request failed");
  }
  return response.json();
}

export function fileUrl(storedFilename) {
  return `${API_BASE}/uploads/${storedFilename}`;
}

export function fetchJobs(search = "") {
  const params = search ? `?search=${encodeURIComponent(search)}` : "";
  return request(`/api/jobs${params}`);
}

export function createJob(formData) {
  return request("/api/jobs", {
    method: "POST",
    body: formData,
  });
}

export function quoteSearch(payload) {
  return request("/api/quote-search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
