import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res =
        mode === "register" ? await api.register(email, password) : await api.login(email, password);
      sessionStorage.setItem("otp_challenge_id", res.challenge_id);
      sessionStorage.setItem("otp_debug", res.otp_debug || "");
      navigate("/otp");
    } catch (err) {
      setError(err.message || "Failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="authWrap">
      <div className="authCard">
        <div className="authHeader">
          <div className="brandRow">
            <div className="brandMark" />
            <div>
              <div className="brandTitle">AI-Powered Speech Pronunciation Coach</div>
              <div className="brandSub">Business pronunciation, faster improvement</div>
            </div>
          </div>
        </div>

        <div className="tabs">
          <button
            type="button"
            className={`tab ${mode === "login" ? "tabActive" : ""}`}
            onClick={() => setMode("login")}
          >
            Login
          </button>
          <button
            type="button"
            className={`tab ${mode === "register" ? "tabActive" : ""}`}
            onClick={() => setMode("register")}
          >
            Sign up
          </button>
        </div>

        <form className="form" onSubmit={onSubmit}>
          <label className="label">
            Email
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
            />
          </label>
          <label className="label">
            Password
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 characters"
              minLength={8}
              required
            />
          </label>

          {error ? <div className="error">{error}</div> : null}

          <button className="primaryBtn" disabled={loading} type="submit">
            {loading ? "Please wait..." : mode === "register" ? "Create account" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}

