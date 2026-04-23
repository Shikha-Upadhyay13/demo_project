"""State schemas for both LangGraph state machines and typed LLM outputs.

Two TypedDicts power the graphs (CourseState, TutorState).
Four Pydantic models power `with_structured_output` calls.
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# ---------- LangGraph state ----------

class CourseState(TypedDict, total=False):
    course_id: str
    topic: str
    videos: list[dict]
    transcripts: list[str]
    vector_collection_name: str
    summary: str
    quiz: list[dict]
    messages: Annotated[list, add_messages]


class TutorState(TypedDict, total=False):
    course_id: str
    user_message: str
    route: str
    retrieved_chunks: list[str]
    answer: str
    messages: Annotated[list, add_messages]


# ---------- Typed LLM outputs ----------

class QuizQuestion(BaseModel):
    q: str = Field(description="The question text.")
    options: list[str] = Field(description="Exactly four answer options.", min_length=4, max_length=4)
    correct_idx: int = Field(description="Index (0-3) of the correct option.", ge=0, le=3)
    explanation: str = Field(description="Brief explanation of why the correct answer is correct.")


class Quiz(BaseModel):
    questions: list[QuizQuestion] = Field(description="Exactly five questions.", min_length=5, max_length=5)


class Summary(BaseModel):
    markdown: str = Field(
        description="Markdown summary covering key concepts, code examples where relevant, and a short next-steps section."
    )


class RouteDecision(BaseModel):
    route: Literal["needs_retrieval", "followup", "unclear", "greeting"] = Field(
        description=(
            "Classification of the user message. "
            "needs_retrieval: a factual question about the course content. "
            "followup: a clarifying request about the previous answer, or chit-chat like 'thanks'. "
            "unclear: too vague to answer without clarification. "
            "greeting: a greeting or opening like 'hi', 'hello', 'hey there'."
        )
    )
