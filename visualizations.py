"""Create static charts from the EDA aggregate CSV outputs.

Run:
    python -m src.visualizations
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EDA_DIR = ROOT / "reports" / "eda"
FIG_DIR = EDA_DIR / "figures"


def require_file(name: str) -> pd.DataFrame:
    path = EDA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run python -m src.eda first.")
    return pd.read_csv(path)


def save_monthly() -> None:
    frame = require_file("monthly_complaints.csv")
    frame = frame.sort_values("date_received")
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(frame["date_received"], frame["complaints"], marker="o")
    ax.set_title("Monthly Published CFPB Complaints with Narratives")
    ax.set_xlabel("Month")
    ax.set_ylabel("Complaints")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "monthly_complaints.png", dpi=160)
    plt.close(fig)


def save_bar(filename: str, column: str, title: str, output: str, top_n: int = 15) -> None:
    frame = require_file(filename).head(top_n).sort_values("complaints")
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(frame[column].astype(str), frame["complaints"])
    ax.set_title(title)
    ax.set_xlabel("Complaints")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIG_DIR / output, dpi=160)
    plt.close(fig)


def save_outcomes() -> None:
    frame = require_file("response_outcomes.csv")
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(frame["company_response_to_consumer"].astype(str), frame["complaints"])
    ax.set_title("Company Response Outcomes")
    ax.set_xlabel("Complaints")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "response_outcomes.png", dpi=160)
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    save_monthly()
    save_bar("product_complaints.csv", "product", "Complaints by Product", "top_products.png")
    save_bar("company_complaints.csv", "company", "Top Companies by Complaint Count", "top_companies.png")
    save_bar("issue_complaints.csv", "issue", "Top Complaint Issues", "top_issues.png")
    save_bar("state_complaints.csv", "state", "Complaints by State", "top_states.png")
    save_outcomes()
    print(f"Charts saved to {FIG_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
