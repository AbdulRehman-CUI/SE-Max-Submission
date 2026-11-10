import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { MotionConfig } from "motion/react";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedLayout } from "./components/Layout";
import { Loading, ToastProvider } from "./components/ui";
import LandingPage from "./pages/LandingPage";
import AuthPage from "./pages/AuthPage";

const Dashboard = lazy(() => import("./pages/DashboardPage"));
const Expenses = lazy(() => import("./pages/ExpensesPage"));
const Budgets = lazy(() => import("./pages/BudgetsPage"));
const Parser = lazy(() => import("./pages/ParserPage"));
const Analytics = lazy(() => import("./pages/AnalyticsPage"));
const Insights = lazy(() => import("./pages/InsightsPage"));
const Settings = lazy(() => import("./pages/SettingsPage"));

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <AuthProvider>
        <ToastProvider>
          <Suspense fallback={<Loading />}>
            <Routes>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<AuthPage key="login" />} />
              <Route
                path="/register"
                element={<AuthPage register key="register" />}
              />
              <Route element={<ProtectedLayout />}>
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/expenses" element={<Expenses />} />
                <Route path="/budgets" element={<Budgets />} />
                <Route path="/ai-assistant" element={<Parser key="text" />} />
                <Route path="/sms-parser" element={<Parser sms key="sms" />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/insights" element={<Insights />} />
                <Route path="/settings" element={<Settings />} />
              </Route>
              <Route
                path="*"
                element={
                  <main className="not-found">
                    <h1>Page not found</h1>
                    <Link className="btn btn-primary" to="/">
                      Back to home
                    </Link>
                  </main>
                }
              />
            </Routes>
          </Suspense>
        </ToastProvider>
      </AuthProvider>
    </MotionConfig>
  );
}
