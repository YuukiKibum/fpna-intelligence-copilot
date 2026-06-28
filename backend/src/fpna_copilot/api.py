from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fpna_copilot.finance_engine.copilot_service import ask_fpna
from fpna_copilot.models import FinanceQuery, FPNAAnswer
from fpna_copilot.ui_spec.ui_spec_builder import build_fpna_answer_from_service_result


app = FastAPI(
    title="FP&A Intelligence Copilot API",
    description="Backend API for deterministic and AI-powered FP&A finance analysis.",
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
    """
    Health check endpoint.
    """

    return {
        "status": "ok",
        "app": "FP&A Intelligence Copilot API",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    """
    API health endpoint.
    """

    return {
        "status": "healthy",
    }


@app.post("/api/chat", response_model=FPNAAnswer)
def chat(query: FinanceQuery) -> FPNAAnswer:
    """
    Main chat endpoint.

    ai_mode = False:
    - deterministic planner decides approved tools

    ai_mode = True:
    - LangGraph AI planner decides approved tools

    In both modes:
    - approved tools calculate using SQLite + pandas
    - response includes generative UI spec
    """

    service_result = ask_fpna(
        question=query.question,
        ai_mode=query.ai_mode,
    )

    return build_fpna_answer_from_service_result(service_result)