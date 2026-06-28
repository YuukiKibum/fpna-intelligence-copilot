from __future__ import annotations

import os
from dotenv import load_dotenv
from typing import Any, Literal, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from fpna_copilot.tools.finance_tools import (
    execute_finance_tool_plan,
    list_finance_tools,
)

load_dotenv()

AllowedToolName = Literal["top_variance", "actual_vs_comparator"]


class AIToolCall(BaseModel):
    """
    One approved finance tool call selected by AI.
    """

    tool_name: AllowedToolName
    args: dict[str, Any] = Field(default_factory=dict)


class AIPlannerOutput(BaseModel):
    """
    Structured planning result from AI.

    AI does not calculate numbers.
    AI only chooses approved tools and arguments.
    """

    can_plan: bool = True
    tool_plan: list[AIToolCall] = Field(default_factory=list)
    reasoning_summary: str = ""


class FPNAAgentState(TypedDict, total=False):
    """
    LangGraph state for AI ON mode.
    """

    question: str
    tool_plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    answer: str
    can_answer: bool
    reflection: str


def _get_llm() -> ChatOpenAI:
    """
    Create the planning LLM.

    OPENAI_API_KEY must exist in environment.
    You can set model using OPENAI_MODEL.
    """

    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1-nano")

    return ChatOpenAI(
        model=model_name,
        temperature=0,
    )


def _build_planner_prompt(question: str) -> str:
    """
    Build instruction prompt for AI planner.
    """

    tools = list_finance_tools()

    return f"""
You are an FP&A AI planning agent.

Your job:
Convert the user question into one or more approved finance tool calls.

Very important rules:
1. Do NOT calculate finance numbers yourself.
2. Do NOT invent columns.
3. Do NOT write SQL.
4. Do NOT write pandas code.
5. Only call approved tools from the tool list.
6. The finance tools will calculate the answer using trusted SQLite + pandas.
7. If the question cannot be mapped to approved tools, return can_plan=false.

Approved tools:
{tools}

Supported metrics:
- revenue
- profit
- cash

Supported period_type:
- in_month
- ytd

Supported comparator values:
- default
- prior
- lbe
- business_plan
- budget
- prior_year
- actual_2025

Business rules:
- If user says "prior" or "prior month" for in_month, use comparator="prior".
  The backend maps this to LBE for the current CT-Narrative sheet.
- If user says "business plan" for ytd, use comparator="budget".
  YTD has Budget columns, not Business Plan columns.
- If user says both in month and ytd, create tool calls for both period types.
- If user says multiple comparators, create multiple tool calls.
- If user says top/highest/largest/worst variance, use top_variance.
- If user says against/vs/compare actual to comparator, use actual_vs_comparator.
- If user mentions a contract like Tamasuk, put it in contract.
- If user mentions a category/country like UAE, KSA, Qatar, put it in category.
- Do not use both category and contract unless the user clearly asks both.

Examples:

Question:
top 5 revenue variance in UAE

Tool plan:
[
  {{
    "tool_name": "top_variance",
    "args": {{
      "metric": "revenue",
      "period_type": "in_month",
      "category": "UAE",
      "contract": null,
      "top_n": 5,
      "direction": "absolute",
      "comparator": "default"
    }}
  }}
]

Question:
Tamasuk in month and ytd revenue against prior month lbe and business plan

Tool plan:
[
  {{
    "tool_name": "actual_vs_comparator",
    "args": {{
      "metric": "revenue",
      "period_type": "in_month",
      "comparator": "prior",
      "contract": "Tamasuk",
      "category": null
    }}
  }},
  {{
    "tool_name": "actual_vs_comparator",
    "args": {{
      "metric": "revenue",
      "period_type": "in_month",
      "comparator": "business_plan",
      "contract": "Tamasuk",
      "category": null
    }}
  }},
  {{
    "tool_name": "actual_vs_comparator",
    "args": {{
      "metric": "revenue",
      "period_type": "ytd",
      "comparator": "budget",
      "contract": "Tamasuk",
      "category": null
    }}
  }}
]

User question:
{question}
"""


def plan_with_ai_node(state: FPNAAgentState) -> FPNAAgentState:
    """
    LangGraph node:
    AI decides which approved finance tools to call.
    """

    question = state.get("question", "")

    if not os.getenv("OPENAI_API_KEY"):
        return {
            **state,
            "can_answer": False,
            "tool_plan": [],
            "reflection": "OPENAI_API_KEY is not configured, so AI planner cannot run.",
        }

    llm = _get_llm()
    structured_llm = llm.with_structured_output(
    AIPlannerOutput,
    method="function_calling",
    )

    prompt = _build_planner_prompt(question)
    planner_output = structured_llm.invoke(prompt)

    tool_plan = [
        {
            "tool_name": call.tool_name,
            "args": call.args,
        }
        for call in planner_output.tool_plan
    ]

    return {
        **state,
        "tool_plan": tool_plan,
        "can_answer": bool(planner_output.can_plan and tool_plan),
        "reflection": planner_output.reasoning_summary,
    }


def execute_tools_node(state: FPNAAgentState) -> FPNAAgentState:
    """
    LangGraph node:
    Execute approved finance tools.
    """

    tool_plan = state.get("tool_plan", [])

    if not tool_plan:
        return {
            **state,
            "can_answer": False,
            "tool_results": [],
            "answer": "I don't know based on the loaded CT-Narrative SQLite data.",
            "reflection": state.get("reflection", "No tool plan was created."),
        }

    tool_results = execute_finance_tool_plan(tool_plan)

    successful = [result for result in tool_results if result.success]

    if not successful:
        return {
            **state,
            "can_answer": False,
            "tool_results": [result.model_dump() for result in tool_results],
            "answer": "I don't know based on the loaded CT-Narrative SQLite data.",
            "reflection": "AI planner created a tool plan, but no finance tool returned a successful answer.",
        }

    answer_text = "\n\n".join(
        str(result.data.get("answer", ""))
        for result in successful
    )

    return {
        **state,
        "can_answer": True,
        "tool_results": [result.model_dump() for result in tool_results],
        "answer": answer_text,
        "reflection": state.get("reflection", "Answered using AI planner and approved finance tools."),
    }


def build_ai_planner_graph():
    """
    Build LangGraph workflow for AI ON mode.
    """

    graph = StateGraph(FPNAAgentState)

    graph.add_node("plan_with_ai", plan_with_ai_node)
    graph.add_node("execute_tools", execute_tools_node)

    graph.add_edge(START, "plan_with_ai")
    graph.add_edge("plan_with_ai", "execute_tools")
    graph.add_edge("execute_tools", END)

    return graph.compile()


ai_planner_graph = build_ai_planner_graph()


def ask_ai_from_sqlite(question: str) -> dict[str, Any]:
    """
    AI ON mode.

    AI chooses approved tools.
    Tools calculate trusted finance results.
    """

    result = ai_planner_graph.invoke(
        {
            "question": question,
            "tool_plan": [],
            "tool_results": [],
            "answer": "",
            "can_answer": False,
            "reflection": "",
        }
    )

    return {
        "can_answer": result.get("can_answer", False),
        "answer": result.get("answer", ""),
        "tool_plan": result.get("tool_plan", []),
        "tool_results": result.get("tool_results", []),
        "reflection": result.get("reflection", ""),
    }