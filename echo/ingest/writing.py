"""Writing sample processor — extracts style signals from free-form text."""

from dataclasses import dataclass


@dataclass
class WritingSample:
    text: str
    word_count: int = 0
    avg_sentence_length: float = 0.0
    vocabulary_richness: float = 0.0


def process_writing(text: str) -> WritingSample:
    """Analyze a writing sample for style signals."""
    sample = WritingSample(text=text)

    words = text.split()
    sample.word_count = len(words)

    # Sentence splitting (rough — split on . ! ?)
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if sentences:
        sentence_lengths = [len(s.split()) for s in sentences]
        sample.avg_sentence_length = sum(sentence_lengths) / len(sentence_lengths)

    # Vocabulary richness = unique words / total words
    if words:
        unique = set(w.lower().strip(".,!?;:\"'()") for w in words)
        sample.vocabulary_richness = len(unique) / len(words)

    return sample
