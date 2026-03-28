import { getToken } from "./auth";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function request(path, { method = "GET", headers, body } = {}) {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body,
  });

  const contentType = res.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : await res.text().catch(() => "");

  if (!res.ok) {
    const message = isJson && data && data.detail ? String(data.detail) : `Request failed: ${res.status}`;
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export const api = {
  health: () => request("/health"),

  register: (email, password) =>
    request("/auth/register", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  login: (email, password) =>
    request("/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  verifyOtp: (challengeId, otp) =>
    request("/auth/verify-otp", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ challenge_id: challengeId, otp }),
    }),

  me: () => request("/auth/me"),

  listLanguages: () => request("/languages"),

  getProfile: () => request("/profile"),
  upsertProfile: (payload) =>
    request("/profile", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    }),

  dashboard: () => request("/sessions/dashboard"),
  listSessions: () => request("/sessions"),

  createSession: ({ language, referenceText, mouthMetrics, audioFile }) => {
    const form = new FormData();
    form.append("language", language);
    if (referenceText) form.append("reference_text", referenceText);
    if (mouthMetrics) form.append("mouth_metrics", JSON.stringify(mouthMetrics));
    form.append("audio", audioFile);
    return request("/sessions", { method: "POST", body: form });
  },

  chat: ({ language, userText }) =>
    request("/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ language, user_text: userText }),
    }),
};

