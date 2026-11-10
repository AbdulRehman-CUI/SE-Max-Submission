import {
  cloneElement,
  createContext,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactElement,
  type ReactNode,
} from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowUpRight,
  Check,
  CircleAlert,
  Inbox,
  LoaderCircle,
  X,
} from "lucide-react";
export function Button({
  children,
  className = "",
  variant = "primary",
  busy = false,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      className={`btn btn-${variant} ${className}`}
      disabled={disabled || busy}
      aria-busy={busy}
      {...props}
    >
      {busy && <LoaderCircle size={17} className="spin" />}
      {children}
    </button>
  );
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactElement<{ id?: string; "aria-describedby"?: string }>;
  hint?: string;
}) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, {
        id,
        "aria-describedby": hint ? `${id}-hint` : undefined,
      })}
      {hint && <small id={`${id}-hint`}>{hint}</small>}
    </div>
  );
}
export function ErrorMessage({
  error,
  retry,
}: {
  error?: string;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <CircleAlert size={18} />
      <div>
        <p>{error}</p>
        {retry && (
          <button className="text-link" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} />
      <span>Loading your data…</span>
    </div>
  );
}
export function Empty({
  title = "A fresh start",
  children,
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Inbox size={24} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  const reduced = useReducedMotion();
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={id}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current && !busy) onClose();
      }}
    >
      <motion.div
        initial={reduced ? false : { opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.18 }}
        className="modal-content"
      >
        <div className="section-heading">
          <h2 id={id}>{title}</h2>
          <Button
            variant="ghost"
            type="button"
            aria-label="Close dialog"
            disabled={busy}
            onClick={onClose}
          >
            <X size={20} />
          </Button>
        </div>
        {children}
      </motion.div>
    </dialog>
  );
}
export function Stat({
  label,
  value,
  note,
  accent = false,
}: {
  label: string;
  value: string | number;
  note: string;
  accent?: boolean;
}) {
  return (
    <motion.div
      className={`stat ${accent ? "stat-accent" : ""}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
    >
      <div className="stat-top">
        <span>{label}</span>
        <ArrowUpRight size={18} />
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </motion.div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {children}
    </div>
  );
}
export function MonthPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="month-picker">
      <span className="sr-only">Select month</span>
      <input
        type="month"
        min="0001-01"
        max="9999-12"
        required
        value={value}
        onChange={(event) => {
          if (/^\d{4}-\d{2}$/.test(event.target.value))
            onChange(event.target.value);
        }}
      />
    </label>
  );
}
const ToastContext = createContext<(message: string) => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [text, setText] = useState("");
  useEffect(() => {
    if (!text) return;
    const timer = setTimeout(() => setText(""), 5000);
    return () => clearTimeout(timer);
  }, [text]);
  return (
    <ToastContext.Provider value={setText}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {text && (
          <div className="toast">
            <Check size={18} />
            {text}
            <button
              aria-label="Dismiss notification"
              onClick={() => setText("")}
            >
              <X size={16} />
            </button>
          </div>
        )}
      </div>
    </ToastContext.Provider>
  );
}
export const useToast = () => useContext(ToastContext);
