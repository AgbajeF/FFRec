"""Fantasy points using the league's own scoring_settings (never assumes PPR)."""

PTS_ALLOW_BUCKETS = [
    (0, 0, "pts_allow_0"), (1, 6, "pts_allow_1_6"), (7, 13, "pts_allow_7_13"),
    (14, 20, "pts_allow_14_20"), (21, 27, "pts_allow_21_27"), (28, 34, "pts_allow_28_34"),
    (35, 999, "pts_allow_35p"),
]
YDS_ALLOW_BUCKETS = [
    (0, 99, "yds_allow_0_100"), (100, 199, "yds_allow_100_199"), (200, 299, "yds_allow_200_299"),
    (300, 349, "yds_allow_300_349"), (350, 399, "yds_allow_350_399"), (400, 449, "yds_allow_400_449"),
    (450, 499, "yds_allow_450_499"), (500, 549, "yds_allow_500_549"), (550, 9999, "yds_allow_550p"),
]


def _bucket(value, buckets):
    for lo, hi, key in buckets:
        if lo <= value <= hi:
            return key
    return None


def fantasy_points(stats, scoring):
    """Sum stat * weight for every scoring key. For team defenses, derive the
    points-allowed / yards-allowed bucket if the stats only carry the raw total."""
    if not stats:
        return 0.0
    total = 0.0
    for key, weight in scoring.items():
        v = stats.get(key)
        if isinstance(v, (int, float)):
            total += v * weight
    for raw_key, buckets in (("pts_allow", PTS_ALLOW_BUCKETS), ("yds_allow", YDS_ALLOW_BUCKETS)):
        if raw_key in stats and not any(b[2] in stats for b in buckets):
            key = _bucket(round(stats[raw_key]), buckets)
            if key and key in scoring:
                total += scoring[key]
    return round(total, 2)


def played(stats):
    if not stats:
        return False
    for k in ("gp", "gms_active", "off_snp", "def_snp", "st_snp"):
        if (stats.get(k) or 0) > 0:
            return True
    return False


def def_stats(weekly, team):
    """Sleeper keys team defenses either as 'KC' or 'TEAM_KC'; prefer the one with defensive fields."""
    a, b = weekly.get(team) or {}, weekly.get(f"TEAM_{team}") or {}
    if "pts_allow" in a or "sack" in a:
        return a
    if "pts_allow" in b or "sack" in b:
        return b
    return a or b
