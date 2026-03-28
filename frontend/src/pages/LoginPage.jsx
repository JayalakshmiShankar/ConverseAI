import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, Lock, Mail } from "lucide-react";
import { api } from "../lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
      <div className="authLayout">
        <div className="authPromo">
          <div className="authPromoTop">
            <div className="brandMark" />
            <div>
              <div className="authPromoBrand">ConverseAI</div>
              <div className="authPromoSub">AI-Powered Speech Pronunciation Coach</div>
            </div>
          </div>
          <div className="authPromoTitle">Speak clearly. Sound confident.</div>
          <div className="authPromoBody">
            Improve pronunciation with language-restricted transcription, phoneme scoring, and mouth movement feedback.
          </div>
          <div className="authPills">
            <span className="pill pillBlue">English (US)</span>
            <span className="pill pillBlue">English (UK)</span>
            <span className="pill pillGreen">Japanese</span>
            <span className="pill pillGreen">German</span>
            <span className="pill pillGreen">Spanish</span>
          </div>
          <div className="authPromoFooter">Secure login → OTP verification → Start practicing</div>
        </div>

        <div className="authCard">
          <div className="authHeader">
            <div className="authTitle">{mode === "login" ? "Login" : "Create account"}</div>
            <div className="authSubtitle">
              {mode === "login" ? "Use your email and password, then verify OTP." : "Create your account, then verify OTP."}
            </div>
          </div>

          <form className="form" onSubmit={onSubmit}>
            <label className="label">
              Email
              <div className="field">
                <span className="fieldIcon" aria-hidden="true">
                  <Mail size={18} />
                </span>
                <input
                  className="input inputWithIcon"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  required
                />
              </div>
            </label>

            <label className="label">
              Password
              <div className="field">
                <span className="fieldIcon" aria-hidden="true">
                  <Lock size={18} />
                </span>
                <input
                  className="input inputWithIcon inputWithRight"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 8 characters"
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  className="fieldAction"
                  onClick={() => setShowPassword((s) => !s)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <div className="authMetaRow">
              <button type="button" className="linkBtn" onClick={() => setError("Forgot password is not enabled yet.")}>
                Forgot password?
              </button>
              <span className="authMetaText">OTP required</span>
            </div>

            {error ? <div className="error">{error}</div> : null}

            <button className="primaryBtn" disabled={loading} type="submit">
              <span>{loading ? "Please wait..." : mode === "register" ? "Create account" : "Continue"}</span>
              <ArrowRight size={18} />
            </button>

            <div className="authSwitch">
              {mode === "login" ? (
                <>
                  <span className="muted">New here?</span>{" "}
                  <button type="button" className="linkBtn" onClick={() => setMode("register")}>
                    Sign up
                  </button>
                </>
              ) : (
                <>
                  <span className="muted">Already a user?</span>{" "}
                  <button type="button" className="linkBtn" onClick={() => setMode("login")}>
                    Login
                  </button>
                </>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
