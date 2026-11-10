import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Category, Trend } from "../types/api";
import { money } from "../lib/format";
import { Empty } from "./ui";
const colors = [
  "#0c785b",
  "#6aa88b",
  "#b0cfad",
  "#dcc68c",
  "#a9b2c5",
  "#677f92",
];
export function TrendChart({ data }: { data: Trend[] }) {
  if (!data.length || data.every((row) => row.transaction_count === 0))
    return (
      <Empty title="Your story starts here">
        Add an expense to see your spending trend.
      </Empty>
    );
  const chart = data.map((row) => ({
    ...row,
    label: new Date(row.year, row.month - 1, 1).toLocaleDateString("en-GB", {
      month: "short",
      year: "2-digit",
    }),
    value: Number(row.total_spent),
  }));
  return (
    <>
      <div
        className="chart"
        role="img"
        aria-label="Monthly spending in PKR. Exact figures follow the chart."
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chart}
            margin={{ top: 15, right: 15, left: 0, bottom: 5 }}
          >
            <defs>
              <linearGradient id="spending-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#238563" stopOpacity={0.22} />
                <stop offset="100%" stopColor="#238563" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#e9eee9" vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11, fill: "#6a756e" }}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11 }}
              tickFormatter={(value) =>
                Number(value) >= 1000
                  ? `${Number(value) / 1000}k`
                  : String(value)
              }
              width={45}
            />
            <Tooltip
              formatter={(_value, _name, item) => [
                money((item.payload as Trend).total_spent),
                "Spent",
              ]}
              contentStyle={{ borderRadius: 12, borderColor: "#e3e9e4" }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#147859"
              fill="url(#spending-fill)"
              strokeWidth={2.5}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <details className="chart-details">
        <summary>View exact monthly amounts</summary>
        <ul>
          {chart.map((row) => (
            <li key={row.label}>
              {row.label}: {money(row.total_spent)}
              {row.is_partial ? " · Month in progress" : ""}
            </li>
          ))}
        </ul>
      </details>
    </>
  );
}
export function CategoryChart({ data }: { data: Category[] }) {
  if (!data.length || data.every((row) => Number(row.total_spent) === 0))
    return (
      <Empty title="No category spending">
        Your categories will appear after you record expenses.
      </Empty>
    );
  return (
    <div className="category-chart">
      <div className="donut" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data.map((row) => ({
                ...row,
                value: Number(row.total_spent),
              }))}
              dataKey="value"
              innerRadius="68%"
              outerRadius="90%"
              paddingAngle={4}
              stroke="none"
              isAnimationActive={false}
            >
              {data.map((_, index) => (
                <Cell key={index} fill={colors[index % colors.length]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="category-legend">
        {data.map((row, index) => (
          <li key={row.category}>
            <span>
              <i style={{ background: colors[index % colors.length] }} />
              {row.category || "Uncategorized"}
            </span>
            <strong>
              {money(row.total_spent)}
              <small>{row.percentage_of_total}%</small>
            </strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
