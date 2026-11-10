from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings


class AIInsightError(RuntimeError):
    pass


class AIService:
    @staticmethod
    def _build_prompt(payload: Dict[str, Any]) -> str:
        return (
            "You are a cautious financial assistant for a PKR-based personal budgeting app. "
            "Use only the supplied numbers and explain them in plain language for a Pakistani student. "
            "Never invent or estimate any financial numbers. If a number is missing, do not state it. "
            "Never provide investment advice, credit advice, or guaranteed financial outcomes. "
            "Return valid JSON with fields: insights, generated_at, status. "
            "Each insight must have keys: type, title, message, priority. "
            "Use only these allowed types: spending_trend, category_spending, budget_utilization, unusual_spending, savings_control. "
            "The response must remain within the supplied facts. "
            f"Financial facts: {json.dumps(payload, default=str, separators=(',', ':'))}"
        )

    @staticmethod
    def _safe_decimal(value: Any) -> Decimal:
        if value is None:
            raise AIInsightError("missing numeric value")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            return Decimal(str(value))
        if isinstance(value, str):
            return Decimal(str(value))
        raise AIInsightError(f"unsupported numeric value: {type(value).__name__}")

    @staticmethod
    def _flatten_numbers(value: Any) -> List[Decimal]:
        numbers: List[Decimal] = []
        if isinstance(value, dict):
            for item in value.values():
                numbers.extend(AIService._flatten_numbers(item))
        elif isinstance(value, list):
            for item in value:
                numbers.extend(AIService._flatten_numbers(item))
        elif isinstance(value, (int, float, Decimal)):
            numbers.append(Decimal(str(value)))
        return numbers

    @staticmethod
    def _validate_insight_numbers(insight: Dict[str, Any], payload: Dict[str, Any]) -> None:
        text = json.dumps(insight, default=str)
        allowed_numbers = [Decimal(str(item)) for item in AIService._flatten_numbers(payload)]
        if not allowed_numbers:
            return

        for number in re.findall(r"-?\d+(?:\.\d+)?", text):
            candidate = Decimal(number)
            if any(abs(candidate - allowed) < Decimal("0.01") for allowed in allowed_numbers):
                continue
            raise AIInsightError(f"unsupported financial number in AI response: {number}")

    @staticmethod
    def _validate_response(payload: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response, dict):
            raise AIInsightError("invalid AI response")
        insights = response.get("insights")
        if not isinstance(insights, list) or not insights:
            raise AIInsightError("empty AI insights")
        for insight in insights:
            if not isinstance(insight, dict):
                raise AIInsightError("invalid insight item")
            for key in ("type", "title", "message", "priority"):
                if not insight.get(key):
                    raise AIInsightError(f"missing insight field: {key}")
            if insight["type"] not in {
                "spending_trend",
                "category_spending",
                "budget_utilization",
                "unusual_spending",
                "savings_control",
            }:
                raise AIInsightError("unsupported insight type")
            AIService._validate_insight_numbers(insight, payload)
        generated_at = response.get("generated_at")
        if not generated_at:
            raise AIInsightError("missing generated_at")
        status = response.get("status")
        if status not in {"success", "fallback"}:
            raise AIInsightError("unsupported status")
        return response

    @staticmethod
    def build_fallback(payload: Dict[str, Any]) -> Dict[str, Any]:
        generated_at = datetime.now(timezone.utc).isoformat()
        insights: List[Dict[str, Any]] = []

        total_spent = payload.get("total_spent", Decimal("0.00"))
        total_transactions = payload.get("total_transactions", 0)
        categories = payload.get("categories") or []
        budgets = payload.get("budgets") or []
        anomalies = payload.get("anomalies") or []

        if total_transactions:
            insights.append({
                "type": "spending_trend",
                "title": "Spending pattern",
                "message": f"You have recorded {total_transactions} transactions totaling PKR {total_spent}.",
                "priority": "medium",
            })
        else:
            insights.append({
                "type": "spending_trend",
                "title": "No spending yet",
                "message": "No expenses have been recorded yet. Start logging your daily transactions to build a clearer spending pattern.",
                "priority": "low",
            })

        if categories:
            top = max(categories, key=lambda item: item.get("total_spent", Decimal("0.00")))
            insights.append({
                "type": "category_spending",
                "title": "Top spending category",
                "message": f"Your highest spending category is {top.get('category', 'Unknown')} with PKR {top.get('total_spent', Decimal('0.00'))}.",
                "priority": "medium",
            })

        if budgets:
            highest_budget = max(budgets, key=lambda item: item.get("utilization_percentage", Decimal("0.00")))
            insights.append({
                "type": "budget_utilization",
                "title": "Budget utilization",
                "message": f"Your most utilized category is {highest_budget.get('category', 'Unknown')} at {highest_budget.get('utilization_percentage', Decimal('0.00'))}% of its budget.",
                "priority": "medium",
            })

        if anomalies:
            insights.append({
                "type": "unusual_spending",
                "title": "Unusual spending detected",
                "message": "A spending anomaly was detected. Review the recent expense entries and confirm whether they were expected.",
                "priority": "high",
            })

        if not insights:
            insights.append({
                "type": "savings_control",
                "title": "Start tracking expenses",
                "message": "Add a few expenses and budgets to unlock personalized financial guidance.",
                "priority": "low",
            })

        return {
            "insights": insights,
            "generated_at": generated_at,
            "status": "fallback",
        }

    @staticmethod
    def get_insights(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not settings.GEMINI_API_KEY:
            return AIService.build_fallback(payload)

        prompt = AIService._build_prompt(payload)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY,
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
                "responseMimeType": "application/json",
            },
        }

        try:
            with httpx.Client(timeout=settings.GEMINI_TIMEOUT_SECONDS) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                candidate = data.get("candidates", [{}])[0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    raise AIInsightError("empty Gemini response")
                text = parts[0].get("text")
                if not text:
                    raise AIInsightError("missing Gemini text")
                cleaned = text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.strip("`\n ")
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:].strip()
                parsed = json.loads(cleaned)
                validated = AIService._validate_response(payload, parsed)
                validated["generated_at"] = datetime.now(timezone.utc).isoformat()
                validated["status"] = "success"
                return validated
        except (httpx.HTTPError, httpx.TimeoutException, TimeoutError, ValueError, TypeError, json.JSONDecodeError, AIInsightError):
            return AIService.build_fallback(payload)
