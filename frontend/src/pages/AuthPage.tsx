import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, ShieldCheck } from "lucide-react";
import { auth } from "../api";
import { useAuth } from "../context/AuthContext";
import { Logo } from "../components/Layout";
import { Button, ErrorMessage, Field, Loading } from "../components/ui";
import { message } from "../lib/format";
export default function AuthPage({ register = false }: { register?: boolean }) {
  const { user, login, loading } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const identifier = String(form.get("identifier")).trim();
    const password = String(form.get("password"));
    if (register && password !== form.get("confirm")) {
      setError("Your passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      if (register && !created) {
        await auth.register(
          identifier,
          String(form.get("email")).trim(),
          password,
        );
        setCreated(true);
      }
      await login(identifier, password);
    } catch (error) {
      setError(message(error));
    } finally {
      setBusy(false);
    }
  }
  if (loading) return <Loading />;
  if (user) return <Navigate to="/dashboard" replace />;
  return (
    <main className="auth-page">
      <div className="auth-story">
        <Logo />
        <div>
          <p className="eyebrow">A FRESH PERSPECTIVE</p>
          <h2>
            Small habits.
            <br />A clearer tomorrow.
          </h2>
          <p>
            Bring your spending into focus, and make more space for the things
            you care about.
          </p>
          <div className="auth-illustration">
            <span>YOUR MONEY, WITH MEANING</span>
            <div>
              {[35, 60, 45, 80, 65, 95, 75].map((height, index) => (
                <i key={index} style={{ height: `${height}%` }} />
              ))}
            </div>
            <p>One expense at a time.</p>
          </div>
        </div>
        <span>Team Git-Up · CUI Tech Fest FA&apos;26</span>
      </div>
      <div className="auth-form-wrap">
        <Link className="back-link" to="/">
          <ArrowLeft size={16} />
          Back to home
        </Link>
        <div className="auth-form">
          <p className="eyebrow">WELCOME TO SPENDSENSE</p>
          <h1>
            {register ? "Your clarity starts here." : "Good to see you again."}
          </h1>
          <p>
            {register
              ? "Create an account and take the first small step."
              : "Sign in to pick up where you left off."}
          </p>
          <form className="form-stack" onSubmit={submit}>
            <ErrorMessage error={error} />
            {created && (
              <p role="status">Your account is ready. Sign in to continue.</p>
            )}
            <fieldset disabled={busy}>
              <Field label={register ? "Username" : "Email or username"}>
                <input
                  name="identifier"
                  autoComplete="username"
                  required
                  minLength={register ? 3 : 1}
                  maxLength={register ? 50 : undefined}
                  pattern={register ? "[\\p{L}\\p{N}_\\-]+" : undefined}
                  placeholder={register ? "Your username" : "you@example.com"}
                />
              </Field>
              {register && (
                <Field label="Email address">
                  <input
                    type="email"
                    name="email"
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                  />
                </Field>
              )}
              <Field
                label="Password"
                hint={register ? "At least 8 characters." : undefined}
              >
                <input
                  type="password"
                  name="password"
                  required
                  minLength={register ? 8 : 1}
                  maxLength={register ? 128 : undefined}
                  autoComplete={register ? "new-password" : "current-password"}
                />
              </Field>
              {register && (
                <Field label="Confirm password">
                  <input
                    name="confirm"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={8}
                    maxLength={128}
                  />
                </Field>
              )}
              <Button busy={busy} className="full-width" type="submit">
                {register && !created ? "Create account" : "Sign in"}
                <ArrowRight size={17} />
              </Button>
            </fieldset>
          </form>
          <p className="auth-switch">
            {register ? "Already have an account?" : "New to SpendSense?"}{" "}
            <Link to={register ? "/login" : "/register"}>
              {register ? "Sign in" : "Create an account"}
            </Link>
          </p>
          <p className="auth-security">
            <ShieldCheck size={16} />A private space for your personal finances.
          </p>
        </div>
      </div>
    </main>
  );
}
