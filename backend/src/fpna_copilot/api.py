from __future__ import annotations

from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fpna_copilot.copilotkit_agent import fpna_agent
from fpna_copilot.finance_engine.copilot_service import ask_fpna
from fpna_copilot.models import FinanceQuery


app = FastAPI(
    title="FP&A Intelligence Copilot API",
    description="Backend API for deterministic, AI-powered, and CopilotKit FP&A finance analysis.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "status": "ok",
        "app": "FP&A Intelligence Copilot API",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
    }


@app.post("/api/finance/query")
def finance_query(query: FinanceQuery) -> dict:
    """
    Data-only finance endpoint.

    This is useful for testing the backend without the frontend.
    It does not return ui_spec.
    """

    return ask_fpna(
        question=query.question,
        ai_mode=query.ai_mode,
    )


add_langgraph_fastapi_endpoint(
    app=app,
    agent=LangGraphAGUIAgent(
        name="fpna_agent",
        description="FP&A intelligence copilot for finance analysis and CopilotKit generative UI.",
        graph=fpna_agent,
    ),
    path="/copilotkit",
)