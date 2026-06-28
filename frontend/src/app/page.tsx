"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  BarChart3,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  History,
  LayoutDashboard,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  TrendingDown,
  TrendingUp,
  Wrench,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type UIComponent = {
  type: string;
  title?: string | null;
  props: Record<string, any>;
};

type ToolPlanItem = {
  tool_name: string;
  args: Record<string, any>;
};

type ToolResult = {
  tool_name: string;
  success: boolean;
  data: Record<string, any>;
  error?: string | null;
};

type FPNAAnswer = {
  answer_text: string;
  tool_results: ToolResult[];
  ui_spec: {
    layout: string;
    components: UIComponent[];
  };
  follow_up_questions: string[];
  assumptions: string[];
  confidence: number | null;
  mode?: "deterministic" | "ai" | null;
  used_fallback?: boolean;
  tool_plan?: ToolPlanItem[];
  reflection?: string | null;
};

type ChatMessage = {
  id: number;
  question: string;
  aiMode: boolean;
  answer: FPNAAnswer;
};

const API_URL = "http://127.0.0.1:8000/api/chat";

function formatAmount(value: unknown) {
  const number = Number(value ?? 0);

  return new Intl.NumberFormat("en-GB", {
    maximumFractionDigits: 1,
  }).format(number);
}

function getVarianceTone(value: unknown) {
  const variance = Number(value ?? 0);

  if (variance > 0) {
    return {
      label: "Favourable",
      text: "text-emerald-700",
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      chart: "#10b981",
      icon: TrendingUp,
    };
  }

  if (variance < 0) {
    return {
      label: "Adverse",
      text: "text-rose-700",
      bg: "bg-rose-50",
      border: "border-rose-200",
      chart: "#ef4444",
      icon: TrendingDown,
    };
  }

  return {
    label: "Neutral",
    text: "text-slate-700",
    bg: "bg-slate-50",
    border: "border-slate-200",
    chart: "#64748b",
    icon: BarChart3,
  };
}

function ModeBadge({
  aiMode,
  answerMode,
  usedFallback,
}: {
  aiMode: boolean;
  answerMode?: "deterministic" | "ai" | null;
  usedFallback?: boolean;
}) {
  if (aiMode) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-3xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-5 shadow-sm"
      >
        <div className="flex items-start gap-3">
          <div className="rounded-2xl bg-emerald-100 p-2 text-emerald-700">
            <BrainCircuit size={20} />
          </div>

          <div>
            <div className="text-sm font-semibold text-emerald-900">
              AI Assisted Mode
            </div>
            <div className="mt-1 text-sm leading-6 text-emerald-800">
              AI interprets the CFO question and chooses the right approved
              finance tools. Calculations still run through controlled SQLite
              and pandas logic.
            </div>

            {usedFallback ? (
              <div className="mt-2 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
                Rule-based fallback was used for this answer.
              </div>
            ) : null}

            {answerMode ? (
              <div className="mt-2 text-xs text-emerald-700">
                Last answer mode: {answerMode}
              </div>
            ) : null}
          </div>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-2xl bg-slate-100 p-2 text-slate-700">
          <ShieldCheck size={20} />
        </div>

        <div>
          <div className="text-sm font-semibold text-slate-900">
            Controlled Rule-Based Mode
          </div>
          <div className="mt-1 text-sm leading-6 text-slate-600">
            The question is interpreted using predefined finance rules. Best for
            repeatable CFO reporting questions and controlled demos.
          </div>

          {answerMode ? (
            <div className="mt-2 text-xs text-slate-500">
              Last answer mode: {answerMode}
            </div>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}

function ExecutiveHero() {
  return (
    <div className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
      <div className="relative bg-gradient-to-br from-slate-950 via-slate-900 to-red-950 p-8 text-white">
        <div className="absolute right-8 top-8 h-28 w-28 rounded-full bg-red-500/20 blur-3xl" />
        <div className="absolute bottom-4 left-1/2 h-24 w-24 rounded-full bg-emerald-400/10 blur-3xl" />

        <div className="relative">
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-red-200">
            <Sparkles size={16} />
            FP&A Intelligence Copilot
          </div>

          <h1 className="mt-3 max-w-3xl text-4xl font-bold leading-tight">
            Finance Narrative AI Assistant
          </h1>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300">
            Ask CFO-style questions over CT-Narrative data. The system returns
            executive commentary, metric cards, variance tables, and dynamic
            charts.
          </p>
        </div>
      </div>
    </div>
  );
}

function ExecutiveSummaryCard({ component }: { component: UIComponent }) {
  const props = component.props;
  const tone = getVarianceTone(props.top_variance);
  const Icon = tone.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            <Sparkles size={16} />
            {component.title}
          </div>

          <h2 className="mt-3 text-2xl font-bold text-slate-950">
            {props.headline}
          </h2>

          <p className="mt-3 text-sm leading-6 text-slate-600">
            {props.question}
          </p>
        </div>

        <div className={`rounded-3xl border ${tone.border} ${tone.bg} p-5`}>
          <div
            className={`flex items-center gap-2 text-sm font-semibold ${tone.text}`}
          >
            <Icon size={18} />
            Top movement
          </div>

          <div className={`mt-2 text-3xl font-bold ${tone.text}`}>
            {formatAmount(props.top_variance)}
          </div>

          <div className="mt-1 text-xs text-slate-500">£&apos;000</div>
        </div>
      </div>
    </motion.div>
  );
}

function KpiStrip({ component }: { component: UIComponent }) {
  const items = component.props.items || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <LayoutDashboard size={20} />
        {component.title}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {items.map((item: any, index: number) => {
          const tone = getVarianceTone(item.variance);
          const Icon = tone.icon;

          return (
            <div
              key={index}
              className={`rounded-3xl border ${tone.border} ${tone.bg} p-4`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">
                    {item.label}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {item.period} · vs {item.comparator_name}
                  </div>
                </div>

                <div className={`rounded-2xl bg-white/70 p-2 ${tone.text}`}>
                  <Icon size={18} />
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="text-slate-500">Actual</div>
                  <div className="mt-1 text-base font-bold text-slate-900">
                    {formatAmount(item.actual)}
                  </div>
                </div>

                <div>
                  <div className="text-slate-500">{item.comparator_name}</div>
                  <div className="mt-1 text-base font-bold text-slate-900">
                    {formatAmount(item.comparator_value)}
                  </div>
                </div>

                <div>
                  <div className="text-slate-500">Variance</div>
                  <div className={`mt-1 text-base font-bold ${tone.text}`}>
                    {formatAmount(item.variance)}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function RankedVarianceChart({ component }: { component: UIComponent }) {
  const rows = component.props.rows || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <BarChart3 size={20} />
        {component.title}
      </div>

      <div className="h-[380px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 8, right: 24, left: 80, bottom: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11, fill: "#475569" }} />
            <YAxis
              type="category"
              dataKey="label"
              width={120}
              tick={{ fontSize: 11, fill: "#475569" }}
            />
            <Tooltip
              formatter={(value: any) => [
                `${formatAmount(value)} £'000`,
                "Variance",
              ]}
              labelStyle={{ color: "#0f172a", fontWeight: 600 }}
            />
            <Bar dataKey="variance" radius={[0, 8, 8, 0]}>
              {rows.map((row: any, index: number) => (
                <Cell
                  key={`ranked-cell-${index}`}
                  fill={getVarianceTone(row.variance).chart}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}

function MetricComparisonCards({ component }: { component: UIComponent }) {
  const cards = component.props.cards || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <BarChart3 size={20} />
        {component.title}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {cards.map((card: any, index: number) => {
          const tone = getVarianceTone(card.variance);
          const Icon = tone.icon;

          return (
            <div key={index} className={`rounded-3xl border ${tone.border} p-5`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-slate-900">
                    {card.title}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    {card.period} · {card.metric}
                  </div>
                </div>

                <div className={`rounded-2xl ${tone.bg} p-2 ${tone.text}`}>
                  <Icon size={18} />
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
                <div>
                  <div className="text-xs text-slate-400">Actual</div>
                  <div className="text-xl font-bold text-slate-900">
                    {formatAmount(card.actual)}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-400">
                    {card.comparator_name}
                  </div>
                  <div className="text-xl font-bold text-slate-900">
                    {formatAmount(card.comparator_value)}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-400">Variance</div>
                  <div className={`text-xl font-bold ${tone.text}`}>
                    {formatAmount(card.variance)}
                  </div>
                </div>

                <div>
                  <div className="text-xs text-slate-400">Tone</div>
                  <div className={`text-xl font-bold ${tone.text}`}>
                    {tone.label}
                  </div>
                </div>
              </div>

              {card.comment ? (
                <div className="mt-4 rounded-2xl bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                  {card.comment}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

function RiskOpportunityCard({ component }: { component: UIComponent }) {
  const props = component.props;
  const adverse = props.biggest_adverse;
  const favourable = props.biggest_favourable;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <TrendingUp size={20} />
        {component.title}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
            <TrendingUp size={18} />
            Biggest opportunity
          </div>

          {favourable ? (
            <>
              <div className="mt-3 text-lg font-bold text-slate-900">
                {favourable.contract || favourable.category || favourable.label}
              </div>
              <div className="mt-1 text-3xl font-bold text-emerald-700">
                {formatAmount(favourable.variance)}
              </div>
              <div className="mt-1 text-xs text-emerald-700">£&apos;000</div>
            </>
          ) : (
            <div className="mt-3 text-sm text-slate-600">
              No favourable movement found in this result.
            </div>
          )}
        </div>

        <div className="rounded-3xl border border-rose-200 bg-rose-50 p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-rose-800">
            <TrendingDown size={18} />
            Biggest risk
          </div>

          {adverse ? (
            <>
              <div className="mt-3 text-lg font-bold text-slate-900">
                {adverse.contract || adverse.category || adverse.label}
              </div>
              <div className="mt-1 text-3xl font-bold text-rose-700">
                {formatAmount(adverse.variance)}
              </div>
              <div className="mt-1 text-xs text-rose-700">£&apos;000</div>
            </>
          ) : (
            <div className="mt-3 text-sm text-slate-600">
              No adverse movement found in this result.
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function EmptyStateCard({ component }: { component: UIComponent }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="text-lg font-semibold text-slate-900">
        {component.title}
      </div>
      <div className="mt-2 text-sm leading-6 text-slate-600">
        {component.props.message}
      </div>
    </div>
  );
}

function MetricCard({ component }: { component: UIComponent }) {
  const props = component.props;
  const variance = Number(props.variance ?? 0);
  const tone = getVarianceTone(variance);
  const Icon = tone.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-3xl border ${tone.border} bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-slate-500">
            {component.title}
          </div>
          <div className="mt-2 text-xs text-slate-400">{props.period}</div>
        </div>

        <div className={`rounded-2xl ${tone.bg} p-2 ${tone.text}`}>
          <Icon size={20} />
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <div className="rounded-2xl bg-slate-50 p-3">
          <div className="text-xs uppercase text-slate-400">Actual</div>
          <div className="mt-1 text-xl font-semibold text-slate-900">
            {formatAmount(props.actual)}
          </div>
        </div>

        <div className="rounded-2xl bg-slate-50 p-3">
          <div className="text-xs uppercase text-slate-400">
            {props.comparator_name}
          </div>
          <div className="mt-1 text-xl font-semibold text-slate-900">
            {formatAmount(props.comparator_value)}
          </div>
        </div>

        <div className={`rounded-2xl ${tone.bg} p-3`}>
          <div className="text-xs uppercase text-slate-400">Variance</div>
          <div className={`mt-1 text-xl font-semibold ${tone.text}`}>
            {formatAmount(props.variance)}
          </div>
        </div>
      </div>

      <div
        className={`mt-4 inline-flex rounded-full px-3 py-1 text-xs font-semibold ${tone.bg} ${tone.text}`}
      >
        {tone.label} · {props.unit}
      </div>

      {props.comment ? (
        <div className="mt-4 rounded-2xl bg-slate-50 p-3 text-sm leading-6 text-slate-600">
          {props.comment}
        </div>
      ) : null}
    </motion.div>
  );
}

function FinanceTable({ component }: { component: UIComponent }) {
  const rows = component.props.rows || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <LayoutDashboard size={20} />
        {component.title}
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-100">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="bg-slate-50 text-xs uppercase text-slate-500">
              <th className="px-4 py-3">Period</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Contract</th>
              <th className="px-4 py-3">Metric</th>
              <th className="px-4 py-3">Actual</th>
              <th className="px-4 py-3">Comparator</th>
              <th className="px-4 py-3">Comparator Value</th>
              <th className="px-4 py-3">Variance</th>
            </tr>
          </thead>

          <tbody>
            {rows.map((row: any, index: number) => {
              const variance = Number(row.variance ?? 0);
              const tone = getVarianceTone(variance);

              return (
                <tr key={index} className="border-t border-slate-100">
                  <td className="px-4 py-4 text-slate-700">
                    {row.period_type}
                  </td>
                  <td className="px-4 py-4 text-slate-700">{row.category}</td>
                  <td className="px-4 py-4 font-medium text-slate-900">
                    {row.contract}
                  </td>
                  <td className="px-4 py-4 text-slate-700">{row.metric}</td>
                  <td className="px-4 py-4 text-slate-700">
                    {formatAmount(row.actual)}
                  </td>
                  <td className="px-4 py-4 text-slate-700">
                    {row.comparator}
                  </td>
                  <td className="px-4 py-4 text-slate-700">
                    {formatAmount(row.comparator_value)}
                  </td>
                  <td className={`px-4 py-4 font-semibold ${tone.text}`}>
                    {formatAmount(row.variance)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}

function VarianceChart({ component }: { component: UIComponent }) {
  const rows = component.props.rows || [];

  const chartRows = rows.map((row: any) => ({
    ...row,
    variance: Number(row.variance ?? 0),
  }));

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <BarChart3 size={20} />
        {component.title}
      </div>

      <div className="h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartRows}
            margin={{ top: 16, right: 16, left: 0, bottom: 80 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              angle={-25}
              textAnchor="end"
              interval={0}
              height={90}
              tick={{ fontSize: 11, fill: "#475569" }}
            />
            <YAxis tick={{ fontSize: 11, fill: "#475569" }} />
            <Tooltip
              formatter={(value: any) => [
                `${formatAmount(value)} £'000`,
                "Variance",
              ]}
              labelStyle={{ color: "#0f172a", fontWeight: 600 }}
            />
            <Bar dataKey="variance" radius={[8, 8, 0, 0]}>
              {chartRows.map((row: any, index: number) => (
                <Cell
                  key={`cell-${index}`}
                  fill={getVarianceTone(row.variance).chart}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}

function CFOInsight({ component }: { component: UIComponent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-3 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <Sparkles size={20} />
        {component.title}
      </div>

      <pre className="whitespace-pre-wrap font-sans text-sm leading-7 text-slate-700">
        {component.props.text}
      </pre>
    </motion.div>
  );
}

function RenderComponent({ component }: { component: UIComponent }) {
  if (component.type === "executive_summary_card") {
    return <ExecutiveSummaryCard component={component} />;
  }

  if (component.type === "kpi_strip") {
    return <KpiStrip component={component} />;
  }

  if (component.type === "ranked_variance_chart") {
    return <RankedVarianceChart component={component} />;
  }

  if (component.type === "metric_comparison_card") {
    return <MetricComparisonCards component={component} />;
  }

  if (component.type === "risk_opportunity_card") {
    return <RiskOpportunityCard component={component} />;
  }

  if (component.type === "empty_state") {
    return <EmptyStateCard component={component} />;
  }

  if (component.type === "cfo_insight") {
    return <CFOInsight component={component} />;
  }

  if (component.type === "metric_card") {
    return <MetricCard component={component} />;
  }

  if (component.type === "table") {
    return <FinanceTable component={component} />;
  }

  if (component.type === "variance_bar_chart") {
    return <VarianceChart component={component} />;
  }

  return null;
}

function DeveloperPanel({ answer }: { answer: FPNAAnswer }) {
  const [open, setOpen] = useState(false);

  const debugData = {
    mode: answer.mode,
    used_fallback: answer.used_fallback,
    confidence: answer.confidence,
    endpoint: API_URL,
    tool_plan: answer.tool_plan,
    reflection: answer.reflection,
    tool_results_summary: answer.tool_results?.map((result) => ({
      tool_name: result.tool_name,
      success: result.success,
      error: result.error,
      columns_used: result.data?.columns_used,
    })),
  };

  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-950 text-white shadow-sm">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-slate-800 p-2 text-slate-200">
            <Wrench size={18} />
          </div>

          <div>
            <div className="text-sm font-semibold">Developer Information</div>
            <div className="text-xs text-slate-400">
              Endpoint, selected tools, columns used, and trace metadata.
            </div>
          </div>
        </div>

        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open ? (
        <pre className="max-h-[500px] overflow-auto border-t border-slate-800 p-5 text-xs leading-5 text-slate-200">
          {JSON.stringify(debugData, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

function AnswerView({
  answer,
  showDeveloperInfo,
}: {
  answer: FPNAAnswer;
  showDeveloperInfo: boolean;
}) {
  const cards = answer.ui_spec.components.filter(
    (component) => component.type === "metric_card"
  );

  const others = answer.ui_spec.components.filter(
    (component) => component.type !== "metric_card"
  );

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
        Layout:{" "}
        <span className="font-semibold text-slate-900">
          {answer.ui_spec.layout}
        </span>{" "}
        · Confidence:{" "}
        <span className="font-semibold text-slate-900">
          {answer.confidence}
        </span>
      </div>

      {cards.length ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          {cards.map((component, index) => (
            <RenderComponent key={index} component={component} />
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6">
        {others.map((component, index) => (
          <RenderComponent key={index} component={component} />
        ))}
      </div>

      {answer.follow_up_questions?.length ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 font-semibold text-slate-900">
            Suggested follow-up questions
          </div>

          <div className="flex flex-wrap gap-3">
            {answer.follow_up_questions.map((item) => (
              <span
                key={item}
                className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {answer.assumptions?.length ? (
        <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 font-semibold text-slate-900">Notes</div>

          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">
            {answer.assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {showDeveloperInfo ? <DeveloperPanel answer={answer} /> : null}
    </section>
  );
}

export default function Home() {
  const [question, setQuestion] = useState(
    "Tamasuk in month and ytd revenue against prior month lbe and business plan"
  );
  const [aiMode, setAiMode] = useState(false);
  const [showDeveloperInfo, setShowDeveloperInfo] = useState(false);
  const [currentAnswer, setCurrentAnswer] = useState<FPNAAnswer | null>(null);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(
    null
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedHistoryItem =
    history.find((item) => item.id === selectedHistoryId) || null;

  const visibleAnswer = selectedHistoryItem?.answer || currentAnswer;

  async function askQuestion(nextQuestion?: string) {
    const finalQuestion = nextQuestion || question;

    if (!finalQuestion.trim()) {
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: finalQuestion,
          ai_mode: aiMode,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data: FPNAAnswer = await response.json();

      const chatMessage: ChatMessage = {
        id: Date.now(),
        question: finalQuestion,
        aiMode,
        answer: data,
      };

      setCurrentAnswer(data);
      setHistory((previous) => [chatMessage, ...previous]);
      setSelectedHistoryId(chatMessage.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  function askSuggestedQuestion(text: string) {
    setQuestion(text);
    askQuestion(text);
  }

  function clearChatHistory() {
    setHistory([]);
    setCurrentAnswer(null);
    setSelectedHistoryId(null);
    setError("");
  }

  return (
    <main className="min-h-screen bg-slate-100 px-6 py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <ExecutiveHero />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[330px_1fr]">
          <aside className="space-y-4">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <History size={18} className="text-slate-500" />
                  <div>
                    <div className="font-semibold text-slate-900">
                      Chat History
                    </div>
                    <div className="text-xs text-slate-500">
                      {history.length} conversation(s)
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    if (history.length === 0) {
                      return;
                    }

                    clearChatHistory();
                  }}
                  aria-disabled={history.length === 0}
                  className={`rounded-full border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 ${
                    history.length === 0 ? "cursor-not-allowed opacity-40" : ""
                  }`}
                  title="Clear history"
                >
                  <Trash2 size={15} />
                </button>
              </div>

              {history.length === 0 ? (
                <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-500">
                  No questions yet. Ask something to start.
                </div>
              ) : (
                <div className="space-y-3">
                  {history.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => setSelectedHistoryId(item.id)}
                      className={`w-full rounded-2xl border p-3 text-left text-sm transition ${
                        selectedHistoryId === item.id
                          ? "border-red-200 bg-red-50"
                          : "border-slate-200 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <div className="line-clamp-2 font-medium text-slate-900">
                        {item.question}
                      </div>

                      <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
                        <span
                          className={`rounded-full px-2 py-1 ${
                            item.aiMode
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {item.aiMode ? "AI Assisted" : "Rule-Based"}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-3 font-semibold text-slate-900">
                Display Options
              </div>

              <label className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-slate-200 p-3">
                <div>
                  <div className="text-sm font-medium text-slate-800">
                    Developer Mode
                  </div>
                  <div className="text-xs leading-5 text-slate-500">
                    Show endpoint, tool plan, and technical trace.
                  </div>
                </div>

                <input
                  type="checkbox"
                  checked={showDeveloperInfo}
                  onChange={(event) =>
                    setShowDeveloperInfo(event.target.checked)
                  }
                  className="h-4 w-4"
                />
              </label>
            </div>
          </aside>

          <div className="space-y-8">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-5 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-lg font-semibold text-slate-900">
                    Ask a finance question
                  </div>
                  <div className="text-sm text-slate-500">
                    Choose controlled rule-based mode or AI assisted mode.
                  </div>
                </div>

                <label className="flex cursor-pointer items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-4 py-2">
                  <span className="text-sm font-medium text-slate-700">
                    AI Assisted
                  </span>
                  <input
                    type="checkbox"
                    checked={aiMode}
                    onChange={(event) => setAiMode(event.target.checked)}
                    className="h-4 w-4"
                  />
                  <span
                    className={`text-sm font-semibold ${
                      aiMode ? "text-emerald-600" : "text-slate-400"
                    }`}
                  >
                    {aiMode ? "ON" : "OFF"}
                  </span>
                </label>
              </div>

              <div className="mb-4">
                <ModeBadge
                  aiMode={aiMode}
                  answerMode={visibleAnswer?.mode}
                  usedFallback={visibleAnswer?.used_fallback}
                />
              </div>

              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={3}
                className="w-full rounded-3xl border border-slate-200 p-5 text-slate-900 outline-none ring-red-200 focus:ring-4"
              />

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={() => askQuestion()}
                  disabled={loading}
                  className="inline-flex items-center gap-2 rounded-2xl bg-red-700 px-5 py-3 font-semibold text-white shadow-sm transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Send size={17} />
                  {loading ? "Analyzing..." : "Ask Copilot"}
                </button>

                <button
                  onClick={() =>
                    askSuggestedQuestion("top 5 revenue variance in UAE")
                  }
                  disabled={loading}
                  className="rounded-2xl border border-slate-200 px-5 py-3 font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  Try UAE top variance
                </button>

                <button
                  onClick={() =>
                    askSuggestedQuestion(
                      "Tamasuk in month and ytd revenue against prior month lbe and business plan"
                    )
                  }
                  disabled={loading}
                  className="rounded-2xl border border-slate-200 px-5 py-3 font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  Try Tamasuk analysis
                </button>
              </div>

              {error ? (
                <div className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">
                  {error}
                </div>
              ) : null}
            </section>

            {visibleAnswer ? (
              <AnswerView
                answer={visibleAnswer}
                showDeveloperInfo={showDeveloperInfo}
              />
            ) : null}
          </div>
        </div>
      </div>
    </main>
  );
}