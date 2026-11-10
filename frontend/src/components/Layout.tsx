import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";
import {
  BarChart3,
  ChartNoAxesColumnIncreasing,
  CircleUserRound,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  ReceiptText,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useAuth } from "../context/AuthContext";
import { Button, Loading, Modal } from "./ui";
const navigation = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/expenses", "Expenses", ReceiptText],
  ["/budgets", "Budgets", Target],
  ["/ai-assistant", "AI Assistant", Sparkles],
  ["/sms-parser", "SMS Parser", MessageSquareText],
  ["/analytics", "Analytics", BarChart3],
  ["/insights", "Insights", ChartNoAxesColumnIncreasing],
  ["/settings", "Settings", CircleUserRound],
] as const;
export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="SpendSense home">
      <span className="logo-mark">
        <ChartNoAxesColumnIncreasing size={23} strokeWidth={2.5} />
      </span>
      SpendSense<span className="logo-dot">.</span>
    </Link>
  );
}
function Navigation({ close }: { close?: () => void }) {
  return (
    <nav aria-label="Main navigation">
      {navigation.map(([path, title, Icon]) => (
        <NavLink key={path} to={path} onClick={close}>
          <Icon size={19} />
          {title}
          {title === "AI Assistant" && <span className="nav-ai">AI</span>}
        </NavLink>
      ))}
    </nav>
  );
}
export function ProtectedLayout() {
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const reduced = useReducedMotion();
  const title =
    navigation.find(([path]) => path === location.pathname)?.[1] ||
    "SpendSense";
  useEffect(() => {
    document.title = `${title} · SpendSense`;
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [title]);
  if (loading) return <Loading />;
  if (!user)
    return <Navigate to="/login" replace />;
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <aside className="sidebar">
        <Logo />
        <p className="nav-label">YOUR WORKSPACE</p>
        <Navigation />
        <div className="sidebar-note">
          <span className="mini-spark">
            <Sparkles size={18} />
          </span>
          <strong>A little clarity, every day.</strong>
          <p>Make room for what matters.</p>
        </div>
        <button className="sidebar-profile" onClick={logout}>
          <span className="avatar">
            {user.username.slice(0, 1).toUpperCase()}
          </span>
          <span>
            <strong>{user.username}</strong>
            <small>Sign out</small>
          </span>
          <LogOut size={17} />
        </button>
      </aside>
      <div className="app-body">
        <header className="app-header">
          <div className="header-title">
            <Button
              variant="ghost"
              className="mobile-menu"
              aria-label="Open navigation"
              onClick={() => setOpen(true)}
            >
              <Menu size={21} />
            </Button>
            <span>{title}</span>
          </div>
          <div className="header-right">
            <time>
              {new Date().toLocaleDateString("en-GB", {
                weekday: "short",
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </time>
            <details className="profile-menu">
              <summary aria-label="Account menu">
                <span className="avatar">
                  {user.username.slice(0, 1).toUpperCase()}
                </span>
                <span>{user.username}</span>
              </summary>
              <div>
                <Link to="/settings">Your profile</Link>
                <button onClick={logout}>Log out</button>
              </div>
            </details>
          </div>
        </header>
        <motion.main
          id="main"
          key={location.pathname}
          initial={reduced ? false : { opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18 }}
        >
          <Outlet />
        </motion.main>
        <footer className="app-footer">
          <span>SpendSense · A clearer picture of your money.</span>
          <span>Team Git-Up</span>
        </footer>
      </div>
      {open && (
        <Modal title="Your workspace" onClose={() => setOpen(false)}>
          <Navigation close={() => setOpen(false)} />
          <Button variant="secondary" onClick={() => setOpen(false)}>
            <X size={16} />
            Close navigation
          </Button>
        </Modal>
      )}
    </div>
  );
}
