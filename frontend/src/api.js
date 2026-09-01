const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function lookupWaterBody(waterBody) {
  return request("/waterbodies/lookup", {
    method: "POST",
    body: JSON.stringify({ water_body: waterBody }),
  });
}

export function createSearch(data) {
  return request("/searches", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function listSearches() {
  return request("/searches");
}

export function getSearch(id) {
  return request(`/searches/${id}`);
}

export function deleteSearch(id) {
  return request(`/searches/${id}`, { method: "DELETE" });
}

export function askQuestion(id, question) {
  return request(`/searches/${id}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
