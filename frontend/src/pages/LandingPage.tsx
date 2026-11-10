import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  MessageSquareText,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { Logo } from "../components/Layout";
const features = [
  [
    ReceiptText,
    "Every expense, in one place.",
    "Keep the little purchases and the big decisions in view. Simple tracking that fits your day.",
    "Smart expense tracking",
  ],
  [
    Target,
    "A plan for your priorities.",
    "Set monthly category budgets and see exactly how much room you have left.",
    "Monthly budgets",
  ],
  [
    Sparkles,
    "Just say what you spent.",
    "Type naturally, in English or Roman Urdu. Review the details, then make it official.",
    "AI expense entry",
  ],
  [
    MessageSquareText,
    "Turn a message into clarity.",
    "Paste a bank or wallet SMS. Review the transaction without giving access to your inbox.",
    "Bank & wallet SMS parsing",
  ],
  [
    BarChart3,
    "See the bigger picture.",
    "Explore your categories and monthly trends. A few clear charts, a lot more perspective.",
    "Spending analytics",
  ],
  [
    TrendingUp,
    "Find your next small step.",
    "Get observations based on your actual spending, with useful context for your habits.",
    "Personalized insights",
  ],
] as const;
function DashboardPreview() {
  return (
    <div className="hero-preview">
      <div className="preview-heading">
        <div className="preview-logo">
          <span className="preview-dot" />
          Your money, at a glance
        </div>
        <span className="preview-label">ILLUSTRATIVE PREVIEW</span>
      </div>
      <div className="preview-welcome">
        <div>
          <small>YOUR MONTHLY OVERVIEW</small>
          <h3>A little more in control.</h3>
        </div>
        <span className="preview-avatar">S</span>
      </div>
      <div className="preview-stats">
        <div>
          <span>Monthly spending</span>
          <strong>
            <small>PKR</small> 24,850<span>.00</span>
          </strong>
          <p>Every rupee has a story.</p>
        </div>
        <div>
          <span>Budget remaining</span>
          <strong>
            <small>PKR</small> 15,150<span>.00</span>
          </strong>
          <p>
            <span className="green-dot" />
            Room for what matters
          </p>
        </div>
      </div>
      <div className="preview-chart-header">
        <strong>Your spending rhythm</strong>
        <span>Last 6 months</span>
      </div>
      <div className="preview-chart">
        <div className="chart-grid-lines">
          <span>30k</span>
          <span>20k</span>
          <span>10k</span>
        </div>
        <svg
          viewBox="0 0 480 150"
          preserveAspectRatio="none"
          aria-label="Illustrative spending trend"
          role="img"
        >
          <defs>
            <linearGradient id="preview-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop stopColor="#67aa83" stopOpacity=".3" />
              <stop offset="1" stopColor="#67aa83" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0 105 C35 105 40 65 85 75 S145 120 180 82 S230 20 275 48 S325 90 365 62 S425 25 480 42 L480 150 L0 150Z"
            fill="url(#preview-gradient)"
          />
          <path
            d="M0 105 C35 105 40 65 85 75 S145 120 180 82 S230 20 275 48 S325 90 365 62 S425 25 480 42"
            fill="none"
            stroke="#167653"
            strokeWidth="3"
          />
        </svg>
      </div>
      <div className="preview-months">
        {["Jun", "Jul", "Aug", "Sep", "Oct", "Nov"].map((month) => (
          <span key={month}>{month}</span>
        ))}
      </div>
      <div className="preview-bottom">
        <span className="preview-check">
          <Check size={18} />
        </span>
        <div>
          <strong>Small habits. Clearer finances.</strong>
          <p>A calmer way to keep track.</p>
        </div>
        <ArrowUpRight size={20} />
      </div>
    </div>
  );
}
export default function LandingPage() {
  const reduced = useReducedMotion();
  const { scrollY } = useScroll();
  const slow = useTransform(scrollY, [0, 1000], [0, 65]);
  const fast = useTransform(scrollY, [0, 1000], [0, -45]);
  const navRef = useRef<HTMLElement>(null);
  useEffect(() => {
    document.title = "SpendSense — Make room for what matters";
    const observer = new IntersectionObserver(([entry]) =>
      navRef.current?.classList.toggle("is-scrolled", !entry.isIntersecting),
    );
    const marker = document.getElementById("scroll-marker");
    if (marker) observer.observe(marker);
    return () => observer.disconnect();
  }, []);
  const enter = (delay: number) => ({
    initial: reduced ? (false as const) : { opacity: 0, y: 25 },
    animate: { opacity: 1, y: 0 },
    transition: {
      duration: reduced ? 0 : 0.9,
      delay: reduced ? 0 : delay,
      ease: "easeOut" as const,
    },
  });
  return (
    <div className="landing">
      <a href="#landing-main" className="skip-link">
        Skip to content
      </a>
      <div id="scroll-marker" />
      <header className="landing-nav" ref={navRef}>
        <div className="landing-container">
          <Logo />
          <nav aria-label="Public navigation">
            <a href="#features" className="nav-section">
              Features
            </a>
            <a href="#about" className="nav-section">
              About
            </a>
            <Link to="/login" className="login-link">
              Log in
            </Link>
            <Link to="/register" className="btn btn-primary">
              Get started <ArrowUpRight size={16} />
            </Link>
          </nav>
        </div>
      </header>
      <main id="landing-main">
        <section className="hero">
          <motion.div
            className="parallax-orb orb-one"
            style={{ y: reduced ? 0 : slow }}
          />
          <motion.div
            className="parallax-orb orb-two"
            style={{ y: reduced ? 0 : fast }}
          />
          <div className="landing-container hero-grid">
            <div className="hero-copy">
              <motion.p className="eyebrow hero-eyebrow" {...enter(0)}>
                <span className="green-dot" />A little clarity goes a long way
              </motion.p>
              <motion.h1 {...enter(0)}>
                SpendSense<span>.</span>
              </motion.h1>
              <motion.h2 {...enter(0.12)}>
                Understand your spending.
                <br />
                <span>Take control of your money.</span>
              </motion.h2>
              <motion.p className="hero-description" {...enter(0.2)}>
                Track expenses, manage budgets, and discover smarter financial
                habits with AI-powered insights.
              </motion.p>
              <motion.div className="hero-actions" {...enter(0.3)}>
                <Link className="btn btn-primary btn-large" to="/register">
                  Get started <ArrowRight size={18} />
                </Link>
                <a className="btn btn-secondary btn-large" href="#features">
                  Explore features <ArrowDown size={16} />
                </a>
              </motion.div>
              <motion.p className="hero-footnote" {...enter(0.4)}>
                <ShieldCheck size={16} />
                Your money. Your perspective. Your pace.
              </motion.p>
            </div>
            <motion.div className="preview-wrap" {...enter(0.3)}>
              <div className="preview-tag">
                <Sparkles size={15} />A clearer picture starts here
              </div>
              <DashboardPreview />
              <span className="preview-caption">
                A preview of what’s possible. Your dashboard uses your data.
              </span>
            </motion.div>
          </div>
          <div className="landing-container hero-strip">
            <span>BUILT AROUND YOUR EVERYDAY</span>
            <span>
              <Check size={15} />
              PKR-first finances
            </span>
            <span>
              <Check size={15} />
              English & Roman Urdu
            </span>
            <span>
              <Check size={15} />
              You confirm every AI entry
            </span>
          </div>
        </section>
        <section className="features-section landing-container" id="features">
          <div className="section-intro">
            <div>
              <p className="eyebrow">LESS GUESSWORK. MORE CLARITY.</p>
              <h2>
                Good with money starts
                <br />
                with knowing your money.
              </h2>
            </div>
            <p>
              All the essentials to build a better relationship with your
              spending. Nothing to get in your way.
            </p>
          </div>
          <div className="feature-grid">
            {features.map(([Icon, title, description, label], index) => (
              <motion.article
                key={title}
                className="feature-card"
                whileHover={reduced ? undefined : { y: -4 }}
              >
                <div className="feature-top">
                  <span className="feature-icon">
                    <Icon size={23} />
                  </span>
                  <span>0{index + 1}</span>
                </div>
                <p className="feature-label">{label}</p>
                <h3>{title}</h3>
                <p>{description}</p>
              </motion.article>
            ))}
          </div>
        </section>
        <section className="how-section" id="about">
          <div className="landing-container">
            <p className="eyebrow">A SIMPLE ROUTINE</p>
            <h2>
              A few small steps.
              <br />A little more peace of mind.
            </h2>
            <div className="steps-grid">
              {[
                [
                  "Record your expenses.",
                  "Add it manually, say it naturally, or paste a transaction message.",
                ],
                [
                  "Set monthly budgets.",
                  "Give your priorities a plan and track your progress as you go.",
                ],
                [
                  "Understand your spending.",
                  "Turn your everyday activity into patterns you can actually use.",
                ],
              ].map(([title, detail], index) => (
                <div className="step" key={title}>
                  <span>0{index + 1}</span>
                  <h3>{title}</h3>
                  <p>{detail}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className="landing-container">
          <div className="landing-cta">
            <div>
              <p className="eyebrow">YOUR NEXT CHAPTER</p>
              <h2>Make room for what matters.</h2>
              <p>
                Start with one expense. Build a clearer picture, day by day.
              </p>
            </div>
            <Link to="/register" className="btn btn-light btn-large">
              Get started <ArrowUpRight size={18} />
            </Link>
          </div>
        </section>
      </main>
      <footer className="landing-footer landing-container">
        <div>
          <Logo />
          <p>AI-Powered Personal Finance Manager.</p>
        </div>
        <div>
          <span>Team Git-Up</span>
          <p>CUI Tech Fest FA&apos;26</p>
        </div>
      </footer>
    </div>
  );
}
