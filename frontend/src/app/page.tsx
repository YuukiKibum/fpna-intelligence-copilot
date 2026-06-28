"use client";

import { FormEvent, useState } from "react";
import { z } from "zod";
import {
  useAgent,
  useCopilotKit,
  useFrontendTool,
} from "@copilotkit/react-core/v2";
import {
  FinanceResult,
  FinanceResultView,
} from "@/components/finance/FinanceResultView";

const financeResultSchema = z.object({
  title: z.string(),
  summary: z.string(),

  metrics: z
    .array(
      z.object({
        label: z.string(),
        value: z.union([z.string(), z.number()]),
        unit: z.string().optional(),
        change: z.union([z.string(), z.number()]).optional(),
        direction: z.enum(["positive", "negative", "neutral"]).optional(),
      }),
    )
    .optional(),

  tables: z
    .array(
      z.object({
        title: z.string(),
        columns: z.array(z.string()),
        rows: z.array(z.record(z.union([z.string(), z.number(), z.null()]))),
      }),
    )
    .optional(),

  charts: z
    .array(
      z.object({
        title: z.string(),
        chart_type: z.enum(["bar", "line"]),
        x_key: z.string(),
        y_key: z.string(),
        data: z.array(z.record(z.union([z.string(), z.number(), z.null()]))),
      }),
    )
    .optional(),

  assumptions: z.array(z.string()).optional(),
  follow_up_questions: z.array(z.string()).optional(),
});

export default function HomePage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<FinanceResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { agent } = useAgent({ agentId: "fpna_agent" });
  const { copilotkit } = useCopilotKit();

  useFrontendTool({
    name: "show_finance_result",
    description:
      "Render the final FP&A analysis result in the dashboard. Use this after fetching and analysing finance data.",
    parameters: financeResultSchema,
    handler: async (financeResult) => {
      setResult(financeResult as FinanceResult);
      return {
        status: "rendered",
        message: "Finance result rendered successfully.",
      };
    },
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion) {
      return;
    }

    setIsSubmitting(true);
    setResult(null);

    try {
      agent.addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: trimmedQuestion,
      });

      await copilotkit.runAgent({ agent });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 px-6 py-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <section className="rounded-3xl bg-[#b5121b] p-8 text-white shadow-sm">
          <p className="text-sm font-medium uppercase tracking-wide opacity-80">
            FP&A Intelligence Copilot
          </p>

          <h1 className="mt-3 text-3xl font-semibold">
            Ask finance questions. Get generated UI.
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 opacity-90">
            The backend agent fetches and analyses the data. CopilotKit then
            renders the result using React components instead of hardcoded UI
            rules.
          </p>
        </section>

        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border bg-white p-4 shadow-sm"
        >
          <div className="flex flex-col gap-3 md:flex-row">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Example: Compare revenue, trading profit and cash for Tamasuk and Khadamat"
              className="min-h-12 flex-1 rounded-xl border px-4 text-sm outline-none focus:border-[#b5121b]"
            />

            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-xl bg-[#b5121b] px-6 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting ? "Analysing..." : "Ask"}
            </button>
          </div>
        </form>

        {result ? (
          <FinanceResultView result={result} />
        ) : (
          <section className="rounded-2xl border border-dashed bg-white p-10 text-center text-sm text-gray-500">
            Ask a question to generate finance cards, charts, tables, and
            commentary.
          </section>
        )}
      </div>
    </main>
  );
}