import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { getSelectedLanguage, setSelectedLanguage } from "../lib/state";

export function LanguagePage() {
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(getSelectedLanguage());
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    api
      .listLanguages()
      .then((d) => mounted && setData(d))
      .catch((e) => mounted && setError(e.message || "Failed to load languages"));
    return () => {
      mounted = false;
    };
  }, []);

  const onPick = (id) => {
    setSelected(id);
    setSelectedLanguage(id);
  };

  return (
    <div>
      <div className="pageTitle">Language</div>
      <div className="muted">Speech processing is strictly restricted to your selected language.</div>
      {error ? <div className="error">{error}</div> : null}

      <div className="gridCards">
        {data?.items?.map((l) => (
          <button
            key={l.id}
            type="button"
            className={`langCard ${selected === l.id ? "langCardActive" : ""}`}
            onClick={() => onPick(l.id)}
          >
            <div className="langTitle">{l.label}</div>
            <div className="langSub">{l.id}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

