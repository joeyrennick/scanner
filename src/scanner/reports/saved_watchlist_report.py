from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


class SavedWatchlistReport:
    def __init__(self, watchlist: dict[str, Any]):
        self.watchlist = watchlist

    def generate(self, pdf_path: Path) -> None:
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        items = self.watchlist.get("items") or []
        page_size = 16
        pages = [items[index:index + page_size] for index in range(0, len(items), page_size)] or [[]]
        with PdfPages(pdf_path) as pdf:
            for page_number, page_items in enumerate(pages, start=1):
                self._page(pdf, page_items, page_number, len(pages))

    def _page(
        self,
        pdf: PdfPages,
        items: list[dict[str, Any]],
        page_number: int,
        page_count: int,
    ) -> None:
        figure = plt.figure(figsize=(11, 8.5))
        figure.text(0.04, 0.94, str(self.watchlist.get("name") or "Saved Watchlist"), fontsize=20, weight="bold")
        figure.text(
            0.04,
            0.905,
            f"{self.watchlist.get('item_count', 0)} saved tickers  •  "
            f"Exported {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')}  •  "
            f"Page {page_number} of {page_count}",
            fontsize=9,
            color="#52606d",
        )

        axes = figure.add_axes([0.03, 0.08, 0.94, 0.78])
        axes.axis("off")
        if items:
            table = axes.table(
                cellText=[_item_row(item) for item in items],
                colLabels=[
                    "Ticker",
                    "Company",
                    "Current Price",
                    "Fair Value",
                    "DCF Upside",
                    "Validation",
                    "Business Quality",
                    "DCF Estimate",
                    "Risk",
                    "Scanner Strategy",
                    "Added",
                ],
                loc="upper center",
                cellLoc="left",
                colLoc="left",
                colWidths=[0.06, 0.15, 0.08, 0.075, 0.075, 0.095, 0.095, 0.095, 0.07, 0.105, 0.08],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(6.5)
            table.scale(1, 1.65)
            for (row, _column), cell in table.get_celld().items():
                if row == 0:
                    cell.set_facecolor("#dceafe")
                    cell.set_text_props(weight="bold", color="#152033")
                elif row % 2 == 0:
                    cell.set_facecolor("#f5f7fa")
                cell.set_edgecolor("#d9e0ea")
        else:
            axes.text(
                0.5,
                0.55,
                "This watchlist does not contain any tickers.",
                ha="center",
                va="center",
                fontsize=13,
                color="#52606d",
            )

        figure.text(
            0.04,
            0.035,
            "Research aid only. Prices and valuation data may be delayed and are not investment advice.",
            fontsize=7.5,
            color="#68737d",
        )
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)


def _item_row(item: dict[str, Any]) -> list[str]:
    data = item.get("data") or {}
    return [
        _text(item.get("ticker") or data.get("Ticker")),
        _text(data.get("Company Name")),
        _money(data.get("Current Price") or data.get("Price")),
        _money(data.get("Fair Value")),
        _percent(data.get("Margin of Safety")),
        _text(data.get("Validation Label") or data.get("Validation Status")),
        _text(data.get("Quality Label")),
        _text(data.get("Valuation Label")),
        _text(data.get("Risk Level")),
        _text(data.get("Triggered Strategies")),
        _date(item.get("added_at")),
    ]


def _text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"n/a", "none", "not calculated"}:
        return "—"
    return text[:40]


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("$", "").replace(",", "").replace("%", "").strip())
        except ValueError:
            return None
    return None


def _money(value: Any) -> str:
    number = _number(value)
    return f"${number:,.2f}" if number is not None else "—"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:.1f}%" if number is not None else "—"


def _date(value: Any) -> str:
    text = str(value or "")
    return text[:10] if text else "—"
