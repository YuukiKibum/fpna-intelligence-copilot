"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";

export type FinanceMetric = {
  label: string;
  value: string | number;
  unit?: string;
  change?: string | number;
  direction?: "positive" | "negative" | "neutral";
};

export type FinanceTable = {
  title: string;
  columns: string[];
  rows: Record<string, string | number | null>[];
};

export type FinanceChart = {
  title: string;
  chart_type: "bar" | "line";
  x_key: string;
  y_key: string;
  data: Record<string, string | number | null>[];
};

export type FinanceResult = {
  title: string;
  summary: string;
  metrics?: FinanceMetric[];
  tables?: FinanceTable[];
  charts?: FinanceChart[];
  assumptions?: string[];
  follow_up_questions?: string[];
};

export function FinanceResultView({ result }: { result: FinanceResult }) {
  return (
    <div className="space-y-6">
      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-semibold text-gray-900">
          {result.title}
        </h1>

        <p className="mt-3 whitespace-pre-line text-sm leading-6 text-gray-700">
          {result.summary}
        </p>
      </section>

      {result.metrics && result.metrics.length > 0 && (
        <section className="grid gap-4 md:grid-cols-3">
          {result.metrics.map((metric, index) => (
            <div
              key={`${metric.label}-${index}`}
              className="rounded-2xl border bg-white p-5 shadow-sm"
            >
              <p className="text-sm text-gray-500">{metric.label}</p>

              <p className="mt-2 text-2xl font-semibold text-gray-900">
                {metric.value}
                {metric.unit ? (
                  <span className="ml-1 text-sm text-gray-500">
                    {metric.unit}
                  </span>
                ) : null}
              </p>

              {metric.change !== undefined && (
                <p
                  className={[
                    "mt-2 text-sm",
                    metric.direction === "positive"
                      ? "text-green-700"
                      : metric.direction === "negative"
                        ? "text-red-700"
                        : "text-gray-600",
                  ].join(" ")}
                >
                  {metric.change}
                </p>
              )}
            </div>
          ))}
        </section>
      )}

      {result.charts?.map((chart, index) => (
        <section
          key={`${chart.title}-${index}`}
          className="rounded-2xl border bg-white p-6 shadow-sm"
        >
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            {chart.title}
          </h2>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {chart.chart_type === "line" ? (
                <LineChart data={chart.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey={chart.x_key} />
                  <YAxis />
                  <Tooltip />
                  <Line dataKey={chart.y_key} strokeWidth={2} />
                </LineChart>
              ) : (
                <BarChart data={chart.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey={chart.x_key} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey={chart.y_key} />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </section>
      ))}

      {result.tables?.map((table, index) => (
        <section
          key={`${table.title}-${index}`}
          className="rounded-2xl border bg-white p-6 shadow-sm"
        >
          <h2 className="mb-4 text-lg font-semibold text-gray-900">
            {table.title}
          </h2>

          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  {table.columns.map((column) => (
                    <th
                      key={column}
                      className="whitespace-nowrap px-4 py-3 text-left font-semibold text-gray-700"
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {table.rows.map((row, rowIndex) => (
                  <tr key={rowIndex} className="border-b">
                    {table.columns.map((column) => (
                      <td
                        key={column}
                        className="whitespace-nowrap px-4 py-3 text-gray-800"
                      >
                        {row[column] ?? "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {result.assumptions && result.assumptions.length > 0 && (
        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Assumptions</h2>

          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-gray-700">
            {result.assumptions.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {result.follow_up_questions && result.follow_up_questions.length > 0 && (
        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">
            Suggested follow-up questions
          </h2>

          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-gray-700">
            {result.follow_up_questions.map((item, index) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}