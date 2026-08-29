from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import textwrap
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


class FundamentalAnalysisReport:
    def __init__(self, analysis: dict[str, Any], page_state: dict[str, Any]):
        self.analysis = analysis
        self.page_state = page_state

    def generate(self, pdf_path: Path, snapshot_path: Path) -> None:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(
                {
                    "snapshot_version": 1,
                    "created_at": datetime.now().astimezone().isoformat(),
                    "analysis": self.analysis,
                    "page_state": self.page_state,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with PdfPages(pdf_path) as pdf:
            self._summary_page(pdf)
            self._validation_page(pdf)
            self._history_page(pdf)

    def _summary_page(self, pdf: PdfPages) -> None:
        company = self.analysis.get("company") or {}
        ticker = str(self.analysis.get("ticker") or "")
        quality = self.analysis.get("quality") or {}
        valuation = self.analysis.get("valuation") or {}
        risk = self.analysis.get("risk") or {}
        validation = self.analysis.get("validation") or {}
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.08, 0.94, "Fundamental Analysis", fontsize=22, weight="bold")
        fig.text(
            0.08,
            0.905,
            f"{company.get('name') or ticker} ({ticker})",
            fontsize=15,
            weight="bold",
        )
        fig.text(
            0.08,
            0.875,
            f"Data as of {self.analysis.get('data_as_of') or 'n/a'}  •  "
            f"Price {_money(self.analysis.get('current_price'))}  •  Source: {self.analysis.get('source', 'n/a')}",
            fontsize=9,
            color="#52606d",
        )
        cards = [
            ("Validation", validation.get("label"), validation.get("score")),
            ("Business Quality", quality.get("label"), quality.get("score")),
            ("DCF Estimate", valuation.get("label"), None),
            ("Risk", risk.get("label"), risk.get("score")),
        ]
        for index, (title, label, score) in enumerate(cards):
            x = 0.08 + index * 0.21
            fig.text(x, 0.82, title, fontsize=10, color="#52606d")
            display = str(label or "unknown").title()
            if score is not None:
                display += f" ({score}/100)"
            fig.text(x, 0.79, display, fontsize=13, weight="bold")

        y = 0.72
        fig.text(0.08, y, "Valuation scenarios", fontsize=13, weight="bold")
        y -= 0.035
        for scenario in valuation.get("scenarios") or []:
            fig.text(
                0.10,
                y,
                f"{str(scenario.get('name', '')).title():5}   "
                f"Fair value {_money(scenario.get('fair_value')):>12}   "
                f"Upside {_percent(scenario.get('upside')):>8}",
                fontsize=10,
                family="monospace",
            )
            y -= 0.028

        for title, checks, good_status in (
            ("Quality checks", quality.get("checks") or [], "pass"),
            ("Risk checks", risk.get("checks") or [], "acceptable"),
        ):
            y -= 0.02
            fig.text(0.08, y, title, fontsize=13, weight="bold")
            y -= 0.035
            for check in checks:
                status = "OK" if check.get("status") == good_status else "REVIEW"
                fig.text(0.10, y, f"{status:7} {check.get('name', '')}", fontsize=9.5)
                y -= 0.026

        fig.text(
            0.08,
            0.035,
            "Research aid only. Estimates depend on provider data and user assumptions and are not investment advice.",
            fontsize=7.5,
            color="#68737d",
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _validation_page(self, pdf: PdfPages) -> None:
        validation = self.analysis.get("validation") or {}
        fig = plt.figure(figsize=(8.5, 11))
        fig.text(0.08, 0.94, "Automated Validation", fontsize=20, weight="bold")
        fig.text(
            0.08,
            0.90,
            f"{validation.get('label') or 'Not calculated'}  •  "
            f"Score {validation.get('score', 'n/a')}/100  •  "
            f"Model {str(validation.get('model') or 'unknown').replace('_', ' ')}",
            fontsize=12,
            weight="bold",
        )
        fig.text(
            0.08,
            0.865,
            "Validation checks data integrity, model fit, quality, risk-adjusted value support, and bear-case resilience.",
            fontsize=9,
            color="#52606d",
        )

        y = 0.82
        for check in validation.get("checks") or []:
            status = str(check.get("status") or "review").upper()
            color = {"PASS": "#15803d", "FAIL": "#b91c1c"}.get(status, "#b45309")
            fig.text(0.08, y, status, fontsize=9, weight="bold", color=color)
            fig.text(0.17, y, str(check.get("name") or ""), fontsize=10, weight="bold")
            fig.text(0.70, y, _validation_value(check.get("value")), fontsize=8.5, ha="right")
            explanation = "\n".join(textwrap.wrap(str(check.get("explanation") or ""), width=100))
            fig.text(0.17, y - 0.017, explanation, fontsize=7.5, color="#52606d", va="top")
            y -= 0.052

        manual_items = validation.get("manual_review_items") or []
        if manual_items:
            y = max(y - 0.01, 0.08)
            fig.text(0.08, y, "Required filing review", fontsize=12, weight="bold")
            y -= 0.03
            for item in manual_items:
                fig.text(0.10, y, f"• {item}", fontsize=8.5)
                y -= 0.026

        fig.text(
            0.08,
            0.035,
            "Automated validation is a research screen. A validated result still requires human review of current SEC filings.",
            fontsize=7.5,
            color="#68737d",
        )
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def _history_page(self, pdf: PdfPages) -> None:
        history = self.analysis.get("financial_history") or []
        fig, axes = plt.subplots(2, 1, figsize=(8.5, 11))
        fig.suptitle("Five-Year Financial History", fontsize=18, weight="bold", y=0.97)
        periods = [str(row.get("fiscal_year") or row.get("period_end") or "") for row in history]
        axes[0].plot(periods, [_billions(row.get("revenue")) for row in history], marker="o", label="Revenue")
        axes[0].plot(periods, [_billions(row.get("free_cash_flow")) for row in history], marker="o", label="Free cash flow")
        axes[0].set_ylabel("USD billions")
        axes[0].grid(alpha=0.25)
        axes[0].legend()
        axes[1].plot(periods, [_percent_value(row.get("gross_margin")) for row in history], marker="o", label="Gross margin")
        axes[1].plot(periods, [_percent_value(row.get("operating_margin")) for row in history], marker="o", label="Operating margin")
        axes[1].set_ylabel("Percent")
        axes[1].grid(alpha=0.25)
        axes[1].legend()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def _money(value) -> str:
    return "n/a" if value is None else f"${float(value):,.2f}"


def _percent(value) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def _billions(value) -> float:
    return 0.0 if value is None else float(value) / 1_000_000_000


def _percent_value(value) -> float:
    return 0.0 if value is None else float(value) * 100


def _validation_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, dict):
        return ", ".join(
            f"{key.replace('_', ' ')}={_compact_number(item)}"
            for key, item in value.items()
        )
    return _compact_number(value)


def _compact_number(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.3g}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)
