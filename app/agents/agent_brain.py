from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class BrainDecision:
    """Explainable result produced by the local job reasoning engine."""

    intent: str
    confidence: float
    target: bool
    reason: str
    matched_signals: tuple[str, ...] = ()
    negative_signals: tuple[str, ...] = ()

    role_score: float = 0.0
    technical_score: float = 0.0
    contradiction_score: float = 0.0
    seniority: str = "unknown"
    evidence_strength: str = "weak"

    candidate_fit_score: float = 0.0
    fit_confidence: float = 0.0
    missing_required_skills: tuple[str, ...] = ()
    eligibility_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LocalAgentBrain:
    """
    Explainable, deterministic, local AI-style job reasoning engine.

    No external APIs, LLM calls, API keys, or network requests.
    """

    ROLE_SIGNALS = {
        "software": (
            "software engineer",
            "software developer",
            "software development",
            "python developer",
            "backend",
            "backend developer",
            "frontend",
            "frontend developer",
            "full stack",
            "full stack developer",
            "developer",
            "devops",
            "qa engineer",
            "test engineer",
        ),
        "embedded": (
            "embedded",
            "embedded systems",
            "embedded engineer",
            "embedded software",
            "firmware",
            "firmware engineer",
            "microcontroller",
            "embedded c",
        ),
        "automation": (
            "automation",
            "automation engineer",
            "industrial automation",
            "controls engineer",
            "control engineer",
            "control systems",
            "plc",
            "scada",
            "instrumentation",
            "instrumentation engineer",
        ),
        "electrical_core": (
            "electrical engineer",
            "electrical engineering",
            "electrical",
            "power engineer",
            "power systems",
            "power electronics",
            "electrical maintenance",
            "maintenance engineer",
            "reliability engineer",
            "condition based maintenance",
            "condition-based maintenance",
            "predictive maintenance",
            "commissioning engineer",
            "testing and commissioning",
            "electrical testing",
        ),
        "energy": (
            "energy engineer",
            "energy engineering",
            "renewable energy",
            "renewable engineer",
            "solar engineer",
            "solar energy",
            "energy management",
            "energy efficiency",
        ),
        "data_ai": (
            "data engineer",
            "data engineering",
            "machine learning engineer",
            "machine learning",
            "ml engineer",
            "ai engineer",
            "artificial intelligence",
            "data science",
        ),
    }

    ROLE_TECHNICAL_SIGNALS = {
        "electrical_core": (
            "electrical",
            "power systems",
            "power electronics",
            "electrical maintenance",
            "electrical testing",
            "transformer",
            "motor",
            "switchgear",
            "protection",
            "relay",
            "circuit breaker",
            "substation",
            "condition based maintenance",
            "predictive maintenance",
            "thermography",
            "vibration analysis",
        ),
        "embedded": (
            "embedded c",
            "microcontroller",
            "firmware",
            "gpio",
            "adc",
            "pwm",
            "spi",
            "i2c",
            "uart",
            "can",
            "rtos",
            "bare metal",
        ),
        "automation": (
            "plc",
            "scada",
            "hmi",
            "industrial automation",
            "instrumentation",
            "ladder logic",
            "pid",
            "control systems",
            "siemens",
            "allen bradley",
        ),
        "software": (
            "python",
            "java",
            "javascript",
            "typescript",
            "backend",
            "frontend",
            "api",
            "rest",
            "sql",
            "git",
            "docker",
            "cloud",
        ),
        "energy": (
            "solar",
            "renewable",
            "energy audit",
            "energy efficiency",
            "power quality",
            "energy management",
            "photovoltaic",
            "pv",
        ),
        "data_ai": (
            "python",
            "machine learning",
            "deep learning",
            "pandas",
            "numpy",
            "tensorflow",
            "pytorch",
            "sql",
            "data analysis",
        ),
    }

    TECHNICAL_DESCRIPTION = (
        "python",
        "embedded",
        "plc",
        "scada",
        "matlab",
        "simulink",
        "power electronics",
        "electrical system",
        "electrical engineering",
        "microcontroller",
        "firmware",
        "software development",
        "sql",
        "automation",
        "control systems",
        "condition-based maintenance",
        "condition based maintenance",
        "predictive maintenance",
        "thermography",
        "vibration analysis",
        "industrial equipment",
        "testing",
        "commissioning",
        "instrumentation",
        "motor",
        "transformer",
        "switchgear",
        "power systems",
        "energy audit",
        "renewable energy",
        "solar",
    )

    NEGATIVE_TITLE = (
        "sales",
        "business development",
        "bd executive",
        "account executive",
        "customer success",
        "customer support",
        "inside sales",
        "field sales",
        "marketing",
        "recruiter",
        "recruitment",
        "human resources",
        "hr executive",
        "talent acquisition",
        "finance",
        "accountant",
        "accounts executive",
        "procurement",
        "purchase executive",
        "administration",
        "admin executive",
        "civil engineer",
        "mechanical engineer",
        "plumbing",
        "electrical sales",
    )

    NEGATIVE_DESCRIPTION = (
        "cold calling",
        "sales target",
        "monthly sales targets",
        "lead generation",
        "sell products",
        "selling products",
        "customer acquisition",
        "business development executive",
        "generate leads",
    )

    CONTRADICTORY_DOMAINS = {
        "plumbing": (
            "plumbing",
            "pipe fitting",
            "water supply",
            "sanitary systems",
        ),
        "civil": (
            "civil engineering",
            "structural engineering",
            "construction engineering",
            "site civil",
        ),
        "mechanical": (
            "mechanical engineering",
            "mechanical design",
            "hvac",
            "automotive engineering",
        ),
        "sales": (
            "sales",
            "cold calling",
            "sales target",
            "lead generation",
        ),
    }

    SENIORITY_SIGNALS = {
        "intern": (
            "intern",
            "internship",
            "apprentice",
        ),
        "entry": (
            "fresher",
            "fresh graduate",
            "graduate engineer trainee",
            "graduate trainee",
            "trainee engineer",
            "get",
            "entry level",
            "entry-level",
            "junior",
            "associate engineer",
            "0-1 year",
            "0 year",
        ),
        "mid": (
            "engineer ii",
            "engineer 2",
            "2-3 years",
            "2+ years",
            "3+ years",
            "mid level",
            "mid-level",
        ),
        "senior": (
            "senior",
            "senior engineer",
            "sr engineer",
            "sr.",
            "lead engineer",
            "lead",
            "principal",
            "architect",
            "manager",
            "head of",
            "director",
        ),
    }

    @staticmethod
    def text(value: Any) -> str:
        return " ".join(
            str(value or "").split()
        ).strip()

    @classmethod
    def _normalize(
        cls,
        value: Any,
    ) -> str:
        return cls.text(value).lower()

    @classmethod
    def _find_signals(
        cls,
        text: str,
        signals: tuple[str, ...],
    ) -> tuple[str, ...]:
        return tuple(
            signal
            for signal in signals
            if signal in text
        )

    @classmethod
    def _role_scores(
        cls,
        title: str,
        description: str,
    ) -> dict[str, float]:
        scores: dict[str, float] = {}

        for role, signals in cls.ROLE_SIGNALS.items():
            score = 0.0

            for signal in signals:
                if signal in title:
                    score += 6.0
                elif signal in description:
                    score += 2.5

            technical_signals = (
                cls.ROLE_TECHNICAL_SIGNALS.get(
                    role,
                    (),
                )
            )

            for signal in technical_signals:
                if signal in title:
                    score += 3.0
                elif signal in description:
                    score += 1.5

            if score > 0:
                scores[role] = score

        return scores

    @classmethod
    def _detect_seniority(
        cls,
        title: str,
        description: str,
    ) -> str:
        title_scores = {
            level: sum(
                1
                for signal in signals
                if signal in title
            )
            for level, signals
            in cls.SENIORITY_SIGNALS.items()
        }

        description_scores = {
            level: sum(
                1
                for signal in signals
                if signal in description
            )
            for level, signals
            in cls.SENIORITY_SIGNALS.items()
        }

        scores = {
            level: (
                title_scores[level] * 3
                + description_scores[level]
            )
            for level in cls.SENIORITY_SIGNALS
        }

        best_level = max(
            scores,
            key=scores.get,
        )

        if scores[best_level] == 0:
            return "unknown"

        return best_level

    @classmethod
    def _contradictions(
        cls,
        title: str,
        description: str,
        role: str | None,
    ) -> tuple[str, ...]:
        contradictions: list[str] = []

        combined = (
            f"{title} {description}"
        )

        for domain, signals in (
            cls.CONTRADICTORY_DOMAINS.items()
        ):
            if any(
                signal in combined
                for signal in signals
            ):
                contradictions.append(domain)

        if (
            role
            and role != "software"
            and "sales" in contradictions
        ):
            return tuple(
                dict.fromkeys(
                    contradictions
                )
            )

        return tuple(
            dict.fromkeys(
                contradictions
            )
        )

    @classmethod
    def evaluate_candidate_fit(
        cls,
        *,
        intent: str,
        confidence: float,
        match_score: float | None = None,
        eligible: bool | None = None,
        missing_required_skills: Any = None,
    ) -> dict[str, Any]:
        """Interpret resume/job matching information."""

        if match_score is None:
            normalized_match = None
        else:
            try:
                normalized_match = max(
                    0.0,
                    min(
                        100.0,
                        float(match_score),
                    ),
                )
            except (
                TypeError,
                ValueError,
            ):
                normalized_match = None

        if eligible is None:
            eligibility_score = 50.0
        elif eligible:
            eligibility_score = 100.0
        else:
            eligibility_score = 0.0

        if isinstance(
            missing_required_skills,
            str,
        ):
            missing = (
                [missing_required_skills]
                if missing_required_skills.strip()
                else []
            )
        elif isinstance(
            missing_required_skills,
            (
                list,
                tuple,
                set,
            ),
        ):
            missing = [
                cls.text(item)
                for item in missing_required_skills
                if cls.text(item)
            ]
        else:
            missing = []

        if normalized_match is None:
            fit_score = 0.0
            fit_confidence = 0.25
            fit_level = "unknown"
        else:
            fit_score = (
                normalized_match * 0.70
                + eligibility_score * 0.30
            )

            if missing:
                penalty = min(
                    30.0,
                    len(missing) * 10.0,
                )
                fit_score -= penalty

            fit_score = max(
                0.0,
                min(
                    100.0,
                    fit_score,
                ),
            )

            fit_confidence = min(
                0.99,
                max(
                    0.30,
                    (
                        confidence * 0.55
                        + normalized_match
                        / 100.0
                        * 0.45
                    ),
                ),
            )

            if fit_score >= 90:
                fit_level = "excellent"
            elif fit_score >= 75:
                fit_level = "strong"
            elif fit_score >= 55:
                fit_level = "moderate"
            else:
                fit_level = "weak"

        reasons: list[str] = []

        if intent not in {
            "non_target",
            "uncertain",
        }:
            reasons.append(
                f"role_fit={intent}"
            )

        if normalized_match is None:
            reasons.append(
                "match_score=unknown"
            )
        else:
            reasons.append(
                f"match_score={normalized_match:.1f}"
            )

        if eligible is True:
            reasons.append(
                "eligibility=confirmed"
            )
        elif eligible is False:
            reasons.append(
                "eligibility=failed"
            )
        else:
            reasons.append(
                "eligibility=unknown"
            )

        if missing:
            reasons.append(
                "missing_required="
                + ", ".join(
                    missing[:5]
                )
            )

        return {
            "candidate_fit_score": round(
                fit_score,
                2,
            ),
            "fit_confidence": round(
                fit_confidence,
                3,
            ),
            "fit_level": fit_level,
            "missing_required_skills": tuple(
                missing
            ),
            "eligibility_score": round(
                eligibility_score,
                2,
            ),
            "fit_reason": "; ".join(
                reasons
            ),
        }

    @classmethod
    def classify_job(
        cls,
        job: Mapping[str, Any],
    ) -> BrainDecision:
        if not isinstance(
            job,
            Mapping,
        ):
            raise TypeError(
                "job must be a mapping."
            )

        title = cls._normalize(
            job.get("title")
            or job.get("job_title")
        )

        description = cls._normalize(
            job.get("description")
        )

        if not title and not description:
            return BrainDecision(
                intent="uncertain",
                confidence=0.0,
                target=False,
                reason=(
                    "job contains no usable title "
                    "or description evidence"
                ),
                evidence_strength="none",
            )

        negative_title = cls._find_signals(
            title,
            cls.NEGATIVE_TITLE,
        )

        negative_description = cls._find_signals(
            description,
            cls.NEGATIVE_DESCRIPTION,
        )

        negative_signals = tuple(
            dict.fromkeys(
                (
                    *negative_title,
                    *negative_description,
                )
            )
        )

        role_scores = cls._role_scores(
            title,
            description,
        )

        technical_hits = tuple(
            dict.fromkeys(
                (
                    *cls._find_signals(
                        title,
                        cls.TECHNICAL_DESCRIPTION,
                    ),
                    *cls._find_signals(
                        description,
                        cls.TECHNICAL_DESCRIPTION,
                    ),
                )
            )
        )

        if role_scores:
            ranked_roles = sorted(
                role_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )

            role, role_score = ranked_roles[0]

            specific_title_role = None

            for (
                candidate_role,
                candidate_signals,
            ) in cls.ROLE_SIGNALS.items():
                if any(
                    signal in title
                    for signal in candidate_signals
                ):
                    specific_title_role = (
                        candidate_role
                    )
                    break

            if (
                specific_title_role is None
                and role_score < 12.0
            ):
                role = None
                role_score = 0.0
        else:
            role = None
            role_score = 0.0

        seniority = cls._detect_seniority(
            title,
            description,
        )

        contradictions = cls._contradictions(
            title,
            description,
            role,
        )

        mixed_domain = any(
            domain in contradictions
            for domain in (
                "plumbing",
                "civil",
                "mechanical",
            )
        )

        if negative_title:
            return BrainDecision(
                intent="non_target",
                confidence=0.99,
                target=False,
                reason=(
                    "title contains excluded role signals: "
                    + ", ".join(
                        negative_title
                    )
                ),
                matched_signals=technical_hits,
                negative_signals=negative_signals,
                role_score=role_score,
                technical_score=float(
                    len(technical_hits)
                ),
                contradiction_score=float(
                    len(contradictions)
                ),
                seniority=seniority,
                evidence_strength="very_strong",
            )

        if mixed_domain:
            return BrainDecision(
                intent="non_target",
                confidence=0.97,
                target=False,
                reason=(
                    "job contains mixed technical domains "
                    "that make automatic targeting unsafe: "
                    + ", ".join(
                        contradictions
                    )
                ),
                matched_signals=technical_hits,
                negative_signals=tuple(
                    dict.fromkeys(
                        (
                            *negative_signals,
                            *contradictions,
                        )
                    )
                ),
                role_score=role_score,
                technical_score=float(
                    len(technical_hits)
                ),
                contradiction_score=float(
                    len(contradictions)
                ),
                seniority=seniority,
                evidence_strength="very_strong",
            )

        if (
            negative_description
            and role is None
        ):
            return BrainDecision(
                intent="non_target",
                confidence=0.96,
                target=False,
                reason=(
                    "description is dominated by "
                    "non-technical sales activity"
                ),
                matched_signals=technical_hits,
                negative_signals=negative_signals,
                role_score=role_score,
                technical_score=float(
                    len(technical_hits)
                ),
                contradiction_score=float(
                    len(contradictions)
                ),
                seniority=seniority,
                evidence_strength="strong",
            )

        if (
            role is None
            and not technical_hits
        ):
            return BrainDecision(
                intent="uncertain",
                confidence=0.25,
                target=False,
                reason=(
                    "insufficient technical or role evidence"
                ),
                matched_signals=(),
                negative_signals=negative_signals,
                role_score=0.0,
                technical_score=0.0,
                contradiction_score=float(
                    len(contradictions)
                ),
                seniority=seniority,
                evidence_strength="none",
            )

        if role is None:
            technical_score = min(
                100.0,
                len(technical_hits) * 12.0,
            )

            confidence = min(
                0.85,
                0.45
                + technical_score / 200.0,
            )

            return BrainDecision(
                intent="technical",
                confidence=round(
                    confidence,
                    3,
                ),
                target=True,
                reason=(
                    "technical evidence detected without "
                    "enough evidence for a specific role family"
                ),
                matched_signals=technical_hits,
                negative_signals=negative_signals,
                role_score=0.0,
                technical_score=technical_score,
                contradiction_score=float(
                    len(contradictions)
                ),
                seniority=seniority,
                evidence_strength=(
                    "strong"
                    if technical_score >= 48
                    else "moderate"
                ),
            )

        technical_hits_for_role = cls._find_signals(
            f"{title} {description}",
            cls.ROLE_TECHNICAL_SIGNALS.get(
                role,
                (),
            ),
        )

        technical_score = min(
            100.0,
            len(
                technical_hits_for_role
            ) * 12.0,
        )

        role_strength = min(
            100.0,
            role_score * 5.0,
        )

        evidence_strength_score = min(
            100.0,
            role_strength * 0.65
            + technical_score * 0.35,
        )

        negative_penalty = min(
            30.0,
            len(
                negative_description
            ) * 10.0,
        )

        confidence = (
            0.45
            + evidence_strength_score / 200.0
            - negative_penalty / 200.0
        )

        confidence = min(
            0.99,
            max(
                0.50,
                confidence,
            ),
        )

        matched = tuple(
            dict.fromkeys(
                (
                    *technical_hits,
                    *technical_hits_for_role,
                    *(
                        signal
                        for signal in cls.ROLE_SIGNALS.get(
                            role,
                            (),
                        )
                        if signal in title
                    ),
                )
            )
        )

        reason_parts = [
            f"technical signals support {role}",
        ]

        if matched:
            reason_parts.append(
                "evidence="
                + ", ".join(
                    matched[:6]
                )
            )

        if seniority != "unknown":
            reason_parts.append(
                f"seniority={seniority}"
            )

        if negative_description:
            reason_parts.append(
                "minor non-technical signals present"
            )

        return BrainDecision(
            intent=role,
            confidence=round(
                confidence,
                3,
            ),
            target=True,
            reason="; ".join(
                reason_parts
            ),
            matched_signals=matched,
            negative_signals=negative_signals,
            role_score=round(
                role_score,
                2,
            ),
            technical_score=round(
                technical_score,
                2,
            ),
            contradiction_score=float(
                len(contradictions)
            ),
            seniority=seniority,
            evidence_strength=(
                "very_strong"
                if evidence_strength_score >= 75
                else (
                    "strong"
                    if evidence_strength_score >= 55
                    else "moderate"
                )
            ),
        )

    @classmethod
    def rank_priority(
        cls,
        *,
        target: bool,
        freshness: float,
        urgency: float,
        match_score: float = 0.0,
        eligibility: float = 100.0,
    ) -> float:
        """
        Calculate bounded adaptive job priority.

        Factors:
            freshness
            urgency
            candidate/job match
            eligibility

        Eligibility:
            100 -> confirmed eligible
            55  -> unknown
            0   -> confirmed ineligible

        Unknown eligibility remains discoverable for REVIEW.
        Confirmed ineligible jobs are strongly suppressed.
        """

        if not target:
            return 0.0

        try:
            freshness = float(
                freshness
            )
        except (
            TypeError,
            ValueError,
        ):
            freshness = 0.0

        try:
            urgency = float(
                urgency
            )
        except (
            TypeError,
            ValueError,
        ):
            urgency = 0.0

        try:
            match_score = float(
                match_score
            )
        except (
            TypeError,
            ValueError,
        ):
            match_score = 0.0

        try:
            eligibility = float(
                eligibility
            )
        except (
            TypeError,
            ValueError,
        ):
            eligibility = 0.0

        freshness = max(
            0.0,
            min(
                100.0,
                freshness,
            ),
        )

        urgency = max(
            0.0,
            min(
                100.0,
                urgency,
            ),
        )

        match_score = max(
            0.0,
            min(
                100.0,
                match_score,
            ),
        )

        eligibility = max(
            0.0,
            min(
                100.0,
                eligibility,
            ),
        )

        base_score = (
            freshness * 0.30
            + urgency * 0.20
            + match_score * 0.35
            + eligibility * 0.15
        )

        if (
            freshness >= 80
            and urgency >= 40
        ):
            base_score += 8.0

        if (
            freshness >= 90
            and urgency >= 80
        ):
            base_score += 7.0

        # Confirmed ineligible.
        if eligibility <= 0:
            base_score *= 0.20

        # Partially known / weak eligibility.
        elif eligibility < 50:
            base_score *= 0.55

        # Unknown eligibility.
        elif eligibility < 75:
            base_score *= 0.80

            # Recent target jobs without matching information
            # must remain discoverable for REVIEW.
            if (
                freshness >= 80
                and match_score <= 0
            ):
                base_score += 6.0

        return round(
            max(
                0.0,
                min(
                    100.0,
                    base_score,
                ),
            ),
            2,
        )

    @classmethod
    def choose_action(
        cls,
        *,
        technical_target: bool,
        eligible: bool,
        score: float | None,
        application_status: str = "",
        match_available: bool = True,
    ) -> str:
        status = cls.text(
            application_status
        ).lower()

        if status in {
            "closed",
            "expired",
            "withdrawn",
            "duplicate",
        }:
            return "SKIP"

        if not technical_target:
            return "SKIP"

        if not eligible:
            return "REVIEW"

        if (
            not match_available
            or score is None
        ):
            return "REVIEW"

        try:
            score_value = float(
                score
            )
        except (
            TypeError,
            ValueError,
        ):
            return "REVIEW"

        if score_value >= 70:
            return "APPLY"

        if score_value >= 55:
            return "REVIEW"

        return "SKIP"


__all__ = [
    "BrainDecision",
    "LocalAgentBrain",
]