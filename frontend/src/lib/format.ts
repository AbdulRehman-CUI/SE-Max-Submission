export function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Karachi",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}
export function money(
  value: string | null | undefined,
  currency = "PKR",
): string {
  if (value == null) return "Unavailable";
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
  return `${negative ? "−" : ""}${currency} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction.padEnd(2, "0").slice(0, 2)}`;
}
export function cents(value: string): bigint {
  const negative = value.startsWith("-");
  const [whole, fraction = ""] = value.replace(/^-/, "").split(".");
  return (
    (BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0").slice(0, 2))) *
    (negative ? -1n : 1n)
  );
}
export function sumMoney(values: string[]): string {
  const sum = values.reduce((total, value) => total + cents(value), 0n);
  const absolute = sum < 0n ? -sum : sum;
  return `${sum < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}
export const validMoney = (value: string, allowZero = false) =>
  /^\d{1,10}(\.\d{1,2})?$/.test(value) && (allowZero || cents(value) > 0n);
export const dateLabel = (value: string) =>
  new Date(`${value}T12:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
export const monthLabel = (value: string) =>
  new Date(`${value}-01T12:00:00`).toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
  });
export const message = (error: unknown) =>
  error instanceof Error ? error.message : "Please try again.";
