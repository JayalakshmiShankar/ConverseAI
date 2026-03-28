import { createElement } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Bot, Gauge, Languages, LogOut, Mic, MessageSquareText, User } from "lucide-react";
import { clearToken } from "../lib/auth";

function NavItem({ to, icon: IconComponent, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => `navItem ${isActive ? "navItemActive" : ""}`}
      end
    >
      {createElement(IconComponent, { size: 18 })}
      <span>{label}</span>
    </NavLink>
  );
}

export function AppShell({ children }) {
  const navigate = useNavigate();

  const onLogout = () => {
    clearToken();
    navigate("/login");
  };

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link className="brand" to="/dashboard">
          <div className="brandMark" />
          <div className="brandText">
            <div className="brandTitle">ConverseAI</div>
            <div className="brandSub">Pronunciation Coach</div>
          </div>
        </Link>

        <nav className="nav">
          <NavItem to="/dashboard" icon={Gauge} label="Dashboard" />
          <NavItem to="/languages" icon={Languages} label="Language" />
          <NavItem to="/record" icon={Mic} label="Record" />
          <NavItem to="/chat" icon={Bot} label="AI Convo" />
          <NavItem to="/feedback" icon={MessageSquareText} label="Feedback" />
          <NavItem to="/profile" icon={User} label="Profile" />
        </nav>

        <button className="logout" type="button" onClick={onLogout}>
          <LogOut size={18} />
          Logout
        </button>
      </aside>

      <main className="main">
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
