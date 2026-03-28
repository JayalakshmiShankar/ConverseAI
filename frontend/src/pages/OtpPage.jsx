import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { setToken } from "../lib/auth";

export function OtpPage() {
  const navigate = useNavigate();
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [otpDebug, setOtpDebug] = useState("");

  useEffect(() => {
    const c = sessionStorage.getItem("otp_challenge_id") || "";
    if (!c) navigate("/login", { replace: true });
    setOtpDebug(sessionStorage.getItem("otp_debug") || "");
  }, [navigate]);

  const onVerify = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const challengeId = sessionStorage.getItem("otp_challenge_id") || "";
      const res = await api.verifyOtp(challengeId, otp);
      setToken(res.access_token);
      sessionStorage.removeItem("otp_challenge_id");
      sessionStorage.removeItem("otp_debug");

      try {
        await api.getProfile();
        navigate("/dashboard", { replace: true });
      } catch {
        navigate("/profile", { replace: true });
      }
    } catch (err) {
      setError(err.message || "OTP verification failed");
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
              <div className="brandTitle">OTP Verification</div>
              <div className="brandSub">Enter the code sent to your email</div>
            </div>
          </div>
        </div>

        {otpDebug ? (
          <div className="hint">
            Dev OTP: <strong>{otpDebug}</strong>
          </div>
        ) : null}

        <form className="form" onSubmit={onVerify}>
          <label className="label">
            OTP
            <input
              className="input"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="6-digit code"
              inputMode="numeric"
              minLength={4}
              maxLength={8}
              required
            />
          </label>

          {error ? <div className="error">{error}</div> : null}

          <button className="primaryBtn" disabled={loading} type="submit">
            {loading ? "Verifying..." : "Verify"}
          </button>
        </form>
      </div>
    </div>
  );
}
