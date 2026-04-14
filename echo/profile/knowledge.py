"""KnowledgeMap builder — what the user knows."""

from echo.ingest.career import CareerHistory
from echo.ingest.linkedin import ConnectionStats, EndorsementStats


def build_knowledge_map(
    endorsements: EndorsementStats | None = None,
    connections: ConnectionStats | None = None,
    career: CareerHistory | None = None,
) -> dict:
    """Build a KnowledgeMap from endorsements, connections, and career data.

    Returns the JSON structure defined in CLAUDE.md:
    - domains[] with name, depth, years, endorsement_count, top_skills, roles_held
    - network with total_connections, top_industries, geographic_center
    """
    domains = []

    if career and career.positions:
        # Group by industry
        industry_data: dict[str, dict] = {}
        for pos in career.positions:
            industry = pos.industry or "General"
            if industry not in industry_data:
                industry_data[industry] = {
                    "name": industry,
                    "roles": [],
                    "start_year": pos.start_year,
                    "end_year": pos.end_year or 2026,
                }
            industry_data[industry]["roles"].append(pos.title)
            industry_data[industry]["end_year"] = max(
                industry_data[industry]["end_year"], pos.end_year or 2026
            )
            industry_data[industry]["start_year"] = min(
                industry_data[industry]["start_year"], pos.start_year
            )

        for industry, data in industry_data.items():
            years = data["end_year"] - data["start_year"]
            # Depth heuristic: years + role diversity
            if years >= 10:
                depth = "expert"
            elif years >= 5:
                depth = "proficient"
            elif years >= 2:
                depth = "practitioner"
            else:
                depth = "beginner"

            # Match endorsements to this domain
            domain_endorsements = 0
            domain_skills: list[str] = []
            if endorsements:
                for skill, count in endorsements.skills.items():
                    # Simple keyword matching for Phase 0
                    if any(
                        kw in skill.lower()
                        for kw in industry.lower().split()
                    ):
                        domain_endorsements += count
                        domain_skills.append(skill)

            domains.append({
                "name": industry,
                "depth": depth,
                "years": years,
                "endorsement_count": domain_endorsements,
                "top_skills": domain_skills[:10],
                "roles_held": data["roles"],
            })

    # Network summary
    network = {
        "total_connections": connections.total_connections if connections else 0,
        "top_industries": [],
        "geographic_center": "",
    }

    if connections and connections.companies:
        # Infer top industries from company names (rough heuristic for Phase 0)
        network["top_industries"] = list(connections.companies.keys())[:5]

    return {
        "domains": sorted(domains, key=lambda d: d["years"], reverse=True),
        "network": network,
    }
