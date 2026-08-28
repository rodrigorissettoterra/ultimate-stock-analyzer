from __future__ import annotations

from dataclasses import dataclass

from ultimate_stock_analyzer.dividends.regularity import DividendProfile


@dataclass(frozen=True, slots=True)
class DividendSustainabilityProfile:
    earnings_payout: float | None
    fcf_payout: float | None
    fcf_coverage: float | None
    stability_score: float | None
    sustainability_score: float
    data_coverage: float
    flags: tuple[str, ...]


def analyze_dividend_sustainability(
    profile: DividendProfile,
    *,
    earnings_per_share_ttm: float | None,
    fcf_per_share_ttm: float | None,
) -> DividendSustainabilityProfile:
    regular_distribution = profile.ttm_regular_amount
    earnings_payout = _positive_ratio(regular_distribution, earnings_per_share_ttm)
    fcf_payout = _positive_ratio(regular_distribution, fcf_per_share_ttm)
    fcf_coverage = _positive_ratio(fcf_per_share_ttm, regular_distribution)

    earnings_component = _payout_component(
        input_value=earnings_per_share_ttm,
        payout=earnings_payout,
        preferred_max=0.80,
        hard_max=1.50,
    )
    fcf_component = _payout_component(
        input_value=fcf_per_share_ttm,
        payout=fcf_payout,
        preferred_max=0.85,
        hard_max=1.35,
    )
    stability_component = _stability_component(profile)
    extraordinary_component = 100.0 * max(0.0, 1.0 - profile.extraordinary_share)

    components: tuple[tuple[float, float | None], ...] = (
        (0.35, profile.regularity_score),
        (0.25, fcf_component),
        (0.15, earnings_component),
        (0.15, stability_component),
        (0.10, extraordinary_component),
    )
    available_weight = sum(weight for weight, value in components if value is not None)
    weighted_total = sum(
        weight * value
        for weight, value in components
        if value is not None
    )
    score = weighted_total / available_weight if available_weight else 0.0
    score = max(0.0, min(100.0, score))

    flags: list[str] = []
    if not profile.qualifies_as_regular_payer:
        flags.append("IRREGULAR_HISTORY")
    if earnings_per_share_ttm is not None and earnings_per_share_ttm <= 0:
        flags.append("NON_POSITIVE_EARNINGS")
    elif earnings_payout is not None and earnings_payout > 1.0:
        flags.append("DISTRIBUTION_EXCEEDS_EARNINGS")
    if fcf_per_share_ttm is not None and fcf_per_share_ttm <= 0:
        flags.append("NON_POSITIVE_FCF")
    elif fcf_payout is not None and fcf_payout > 1.0:
        flags.append("DISTRIBUTION_EXCEEDS_FCF")
    if profile.extraordinary_share > 0.35:
        flags.append("HIGH_EXTRAORDINARY_DEPENDENCE")
    completed_pairs = max(0, len(profile.completed_annual_amounts) - 1)
    if completed_pairs >= 2 and profile.cut_years / completed_pairs >= 0.5:
        flags.append("FREQUENT_DISTRIBUTION_CUTS")
    if available_weight < 0.75:
        flags.append("LOW_SUSTAINABILITY_DATA_COVERAGE")

    return DividendSustainabilityProfile(
        earnings_payout=earnings_payout,
        fcf_payout=fcf_payout,
        fcf_coverage=fcf_coverage,
        stability_score=stability_component,
        sustainability_score=score,
        data_coverage=available_weight,
        flags=tuple(flags),
    )


def _positive_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _payout_component(
    *,
    input_value: float | None,
    payout: float | None,
    preferred_max: float,
    hard_max: float,
) -> float | None:
    if input_value is None:
        return None
    if input_value <= 0:
        return 0.0
    if payout is None or payout < 0:
        return 0.0
    if payout <= preferred_max:
        return 100.0
    if payout >= hard_max:
        return 0.0
    return 100.0 * (hard_max - payout) / (hard_max - preferred_max)


def _stability_component(profile: DividendProfile) -> float | None:
    annual = profile.completed_annual_amounts
    if len(annual) < 2 or profile.annual_amount_cv is None:
        return None
    pairs = len(annual) - 1
    cut_component = 100.0 * max(0.0, 1.0 - profile.cut_years / pairs)
    cv_component = 100.0 * max(0.0, 1.0 - min(profile.annual_amount_cv, 1.0))
    return (cut_component + cv_component) / 2.0
