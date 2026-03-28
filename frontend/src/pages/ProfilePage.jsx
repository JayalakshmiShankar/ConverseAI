import { useEffect, useState } from "react";
import { api } from "../lib/api";

export function ProfilePage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const [form, setForm] = useState({
    name: "",
    date_of_birth: "",
    gender: "Prefer not to say",
    mobile_number: "",
  });

  useEffect(() => {
    let mounted = true;
    api
      .getProfile()
      .then((p) => {
        if (!mounted) return;
        setForm({
          name: p.name || "",
          date_of_birth: p.date_of_birth || "",
          gender: p.gender || "Prefer not to say",
          mobile_number: p.mobile_number || "",
        });
      })
      .catch(() => {})
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, []);

  const setField = (k, v) => setForm((s) => ({ ...s, [k]: v }));

  const onSave = async (e) => {
    e.preventDefault();
    setError("");
    setOk("");
    setSaving(true);
    try {
      await api.upsertProfile(form);
      setOk("Profile saved");
    } catch (err) {
      setError(err.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="pageTitle">Loading profile...</div>;

  return (
    <div>
      <div className="pageTitle">Profile</div>
      <div className="card">
        <form className="formGrid" onSubmit={onSave}>
          <label className="label">
            Name
            <input className="input" value={form.name} onChange={(e) => setField("name", e.target.value)} required />
          </label>

          <label className="label">
            Date of Birth
            <input
              className="input"
              type="date"
              value={form.date_of_birth}
              onChange={(e) => setField("date_of_birth", e.target.value)}
              required
            />
          </label>

          <label className="label">
            Gender
            <select className="input" value={form.gender} onChange={(e) => setField("gender", e.target.value)}>
              <option>Prefer not to say</option>
              <option>Female</option>
              <option>Male</option>
              <option>Non-binary</option>
            </select>
          </label>

          <label className="label">
            Mobile number
            <input
              className="input"
              value={form.mobile_number}
              onChange={(e) => setField("mobile_number", e.target.value)}
              required
            />
          </label>

          {error ? <div className="error">{error}</div> : null}
          {ok ? <div className="ok">{ok}</div> : null}

          <button className="primaryBtn" type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
        </form>
      </div>
    </div>
  );
}

