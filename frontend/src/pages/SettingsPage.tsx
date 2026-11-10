import { LogOut, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Button, PageHeading } from "../components/ui";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <>
      <PageHeading
        eyebrow="YOUR WORKSPACE"
        title="Profile & settings"
        description="Your account details and SpendSense defaults."
      />
      <section className="card panel profile-card">
        <h2>
          <UserRound size={20} />
          Account information
        </h2>
        <dl className="detail-list">
          <div>
            <dt>Username</dt>
            <dd>{user.username}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Member since</dt>
            <dd>
              {new Date(user.created_at).toLocaleDateString("en-GB", {
                year: "numeric",
                month: "long",
                day: "numeric",
                timeZone: "Asia/Karachi",
              })}
            </dd>
          </div>
          <div>
            <dt>Default currency</dt>
            <dd>PKR · Pakistani rupee</dd>
          </div>
          <div>
            <dt>Reporting timezone</dt>
            <dd>Asia/Karachi</dd>
          </div>
        </dl>
        <Button variant="secondary" onClick={logout}>
          <LogOut size={18} />
          Log out
        </Button>
      </section>
    </>
  );
}
