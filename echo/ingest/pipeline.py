"""Ingest pipeline orchestrator — coordinates parsing and profile building."""

from echo.ingest.career import CareerHistory, parse_career
from echo.ingest.linkedin import (
    ConnectionStats,
    EndorsementStats,
    MessageStats,
    parse_connections,
    parse_endorsements,
    parse_messages,
)
from echo.ingest.writing import WritingSample, process_writing


class IngestPipeline:
    """Orchestrates the full ingest flow for a user.

    Collects parsed data from all sources and hands it to the profile builders.
    """

    def __init__(self, user_name: str):
        self.user_name = user_name
        self.message_stats: MessageStats | None = None
        self.endorsement_stats: EndorsementStats | None = None
        self.connection_stats: ConnectionStats | None = None
        self.career_history: CareerHistory | None = None
        self.writing_samples: list[WritingSample] = []

    def ingest_messages(self, csv_content: str) -> MessageStats:
        self.message_stats = parse_messages(csv_content, self.user_name)
        return self.message_stats

    def ingest_endorsements(self, csv_content: str) -> EndorsementStats:
        self.endorsement_stats = parse_endorsements(csv_content)
        return self.endorsement_stats

    def ingest_connections(self, csv_content: str) -> ConnectionStats:
        self.connection_stats = parse_connections(csv_content)
        return self.connection_stats

    def ingest_career(self, career_data: dict) -> CareerHistory:
        self.career_history = parse_career(career_data)
        return self.career_history

    def ingest_writing(self, text: str) -> WritingSample:
        sample = process_writing(text)
        self.writing_samples.append(sample)
        return sample

    def is_ready_for_profile(self) -> bool:
        """Check if we have enough data to build a profile."""
        return self.message_stats is not None and self.message_stats.user_messages > 0
