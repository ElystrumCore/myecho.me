"""Career history parser — structured JSON input."""

from dataclasses import dataclass, field


@dataclass
class CareerPosition:
    title: str
    company: str
    start_year: int
    end_year: int | None = None  # None = current
    industry: str = ""
    description: str = ""


@dataclass
class CareerHistory:
    positions: list[CareerPosition] = field(default_factory=list)
    total_years: int = 0
    industries: list[str] = field(default_factory=list)
    trajectory: list[str] = field(default_factory=list)


def parse_career(data: dict) -> CareerHistory:
    """Parse career history from structured JSON.

    Expected format:
    {
        "positions": [
            {
                "title": "Pipefitter Apprentice",
                "company": "Company A",
                "start_year": 2005,
                "end_year": 2008,
                "industry": "Oil & Gas",
                "description": "..."
            },
            ...
        ]
    }
    """
    history = CareerHistory()
    raw_positions = data.get("positions", [])

    for pos_data in raw_positions:
        position = CareerPosition(
            title=pos_data.get("title", ""),
            company=pos_data.get("company", ""),
            start_year=pos_data.get("start_year", 0),
            end_year=pos_data.get("end_year"),
            industry=pos_data.get("industry", ""),
            description=pos_data.get("description", ""),
        )
        history.positions.append(position)

    # Sort by start year
    history.positions.sort(key=lambda p: p.start_year)

    # Derive trajectory (title progression)
    history.trajectory = [p.title for p in history.positions]

    # Derive industries
    industries = list(dict.fromkeys(p.industry for p in history.positions if p.industry))
    history.industries = industries

    # Total years
    if history.positions:
        earliest = history.positions[0].start_year
        latest_end = max(p.end_year or 2026 for p in history.positions)
        history.total_years = latest_end - earliest

    return history
