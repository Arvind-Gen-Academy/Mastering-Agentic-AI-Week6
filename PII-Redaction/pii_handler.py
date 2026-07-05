import re

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

# Words that would otherwise match the standalone Title-Case name fallback
# pattern (short, capitalized, no other recognizer claims them) but are common
# non-name answers in this app's conversation flow.
_NON_NAME_WORDS = {
    "yes", "no", "none", "ok", "okay", "sure", "na", "n/a",
    "male", "female", "non-binary", "nonbinary", "transgender", "trans",
    "general medicine", "cardiology", "orthopedics", "neurology", "pediatrics",
    "dermatology", "ophthalmology", "ent", "gynecology", "psychiatry",
}


class PIIHandler:
    """PII detection and redaction via Microsoft Presidio.

    Maintains a per-session entity map so the same original value always maps to
    the same numbered token (e.g. "John Smith" → <PERSON_0> consistently across
    multiple conversation turns).
    """

    ENTITIES = [
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "CREDIT_CARD",
        "US_SSN",
        "IP_ADDRESS",
        "MEDICAL_LICENSE",
        "IBAN_CODE",
        "NRP",
        "AGE",
        "SEX",
    ]

    def __init__(self) -> None:
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

        # Age: "25 years old", "aged 25", "I am 30", "I'm 30", "age is 25",
        # "Age: 25", or a bare number given as a standalone answer (e.g. the
        # patient replying "34" when asked "What is your age?").
        age_recognizer = PatternRecognizer(
            supported_entity="AGE",
            patterns=[
                Pattern("age_years_old", r"\b\d{1,3}\s*(?:years?\s*old|yr\.?\s*old|y\.?o\.?)\b", 0.9),
                Pattern("age_context",   r"\b(?:age[d]?|am|i'm|i\s+am)\s*(?:is|:|-)?\s+\d{1,3}\b", 0.85),
                Pattern("age_standalone", r"^\s*\d{1,3}\s*$", 0.6),
            ],
            global_regex_flags=re.IGNORECASE,
        )
        # Sex/gender keywords
        sex_recognizer = PatternRecognizer(
            supported_entity="SEX",
            patterns=[
                Pattern("sex_keyword", r"\b(?:male|female|non-binary|nonbinary|transgender|trans)\b", 0.85),
            ],
            global_regex_flags=re.IGNORECASE,
        )
        # Name: spaCy's statistical PERSON model has patchy recall on names outside
        # its training distribution (e.g. many South Asian / Arabic given names come
        # back with zero candidates, not just low confidence). This catches a bare
        # 1-4 word Title-Case reply as a fallback — validate_result filters out
        # non-name words (department names, yes/no/etc.) that would otherwise match.
        name_recognizer = PatternRecognizer(
            supported_entity="PERSON",
            patterns=[
                Pattern("name_standalone", r"^[A-Z][a-zA-Z'-]*(?:\s+[A-Z][a-zA-Z'-]*){0,3}$", 0.6),
            ],
            global_regex_flags=0,
        )
        name_recognizer.validate_result = (
            lambda text: False if text.strip().lower() in _NON_NAME_WORDS else None
        )

        # Phone: catches Indian 10-digit mobiles (6–9 prefix) regardless of NLP context.
        # Presidio's built-in recognizer is context-sensitive and misses corrections
        # like "actually it's 9999888877" when there's little surrounding text.
        phone_recognizer = PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            patterns=[
                Pattern("india_mobile",    r"(?<!\d)(?:\+91|0)?[6-9]\d{9}(?!\d)", 0.85),
                Pattern("intl_with_plus",  r"\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}", 0.80),
            ],
        )
        self.analyzer.registry.add_recognizer(age_recognizer)
        self.analyzer.registry.add_recognizer(sex_recognizer)
        self.analyzer.registry.add_recognizer(phone_recognizer)
        self.analyzer.registry.add_recognizer(name_recognizer)
        self._entity_map: dict[str, str] = {}   # token → original
        self._counters: dict[str, int] = {}      # entity_type → next index

    # ------------------------------------------------------------------
    # Core redaction
    # ------------------------------------------------------------------

    def redact(self, text: str) -> str:
        """Replace detected PII with stable numbered tokens.

        The same original string always gets the same token within a session.
        """
        if not text or not text.strip():
            return text

        results = self.analyzer.analyze(
            text=text,
            language="en",
            entities=self.ENTITIES,
        )

        if not results:
            return text

        # Multiple patterns (e.g. AGE's several rules) can match overlapping
        # spans. Resolve overlaps by keeping the highest-scoring (then longest)
        # match and dropping any span that overlaps an already-kept one —
        # otherwise splicing overlapping spans corrupts the output text.
        by_priority = sorted(results, key=lambda r: (-r.score, -(r.end - r.start)))
        kept: list = []
        for r in by_priority:
            if not any(r.start < k.end and k.start < r.end for k in kept):
                kept.append(r)

        # Sort descending by start so right-to-left replacement keeps offsets valid
        sorted_results = sorted(kept, key=lambda r: r.start, reverse=True)

        result_text = text
        for result in sorted_results:
            original = text[result.start : result.end]

            # Reuse existing token for the same original value (case-sensitive)
            existing = next(
                (tok for tok, orig in self._entity_map.items() if orig == original),
                None,
            )
            if existing:
                token = existing
            else:
                idx = self._counters.get(result.entity_type, 0)
                token = f"TOKEN_{result.entity_type}_{idx}"
                self._counters[result.entity_type] = idx + 1
                self._entity_map[token] = original

            result_text = (
                result_text[: result.start] + token + result_text[result.end :]
            )

        return result_text

    # ------------------------------------------------------------------
    # De-anonymization (display only — never log or export)
    # ------------------------------------------------------------------

    def deredact(self, text: str) -> str:
        """Restore original values using the session entity map."""
        for token, original in self._entity_map.items():
            text = text.replace(token, original)
        return text

    def deredact_info(self, patient_info: dict) -> dict:
        """De-anonymize all string fields of the patient info dict for display."""
        return {
            k: (self.deredact(v) if isinstance(v, str) else v)
            for k, v in patient_info.items()
        }

    # ------------------------------------------------------------------
    # Export redaction
    # ------------------------------------------------------------------

    def redact_info_for_export(self, display_info: dict) -> dict:
        """Return patient info with PII-bearing fields re-redacted for safe export.

        Operates on already-de-anonymized values (display_info) so that even
        values that slipped through Presidio in the original text are caught here.
        """
        pii_fields = {"name", "doctor"}
        return {
            k: (self.redact(str(v)) if k in pii_fields and v else v)
            for k, v in display_info.items()
        }

    def get_entity_map(self) -> dict:
        return dict(self._entity_map)
