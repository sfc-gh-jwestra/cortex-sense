"""
Deterministic checks of agent SQL against the Cortex Sense feedback rules (scripts/record_feedback.py).

Each check looks for a known wrong pattern (fail) or the rule's correct pattern (pass) and
returns nothing when the SQL doesn't touch that rule. Used by build_web_data.py (recorded eval
traces) and app/web/api_server.py (live runs), so both show the same flags.

    from rule_checks import check_sql
    check_sql(sql) -> [{"rule": ..., "status": "pass" | "fail", "reason": ...}]

Self-test: python3 scripts/rule_checks.py   (every query in prime_query_history.py must pass)
"""
import re

_FLAGS = re.IGNORECASE | re.DOTALL


def _has(pattern, sql):
    return re.search(pattern, sql, _FLAGS) is not None


def _norm(sql):
    # Drop comments and string literals so 'launch' in a CASE label isn't read as a filter.
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def _sales_to_catalog(sql):
    touches_catalog = _has(r"GAME_CATALOG\.", sql)
    uses_title_link = _has(r"\bCATALOG_GAME_ID\b", sql)
    if not (touches_catalog and uses_title_link):
        return None
    # TITLES.CATALOG_GAME_ID: alias.CATALOG_GAME_ID where alias is bound to GAME_SALES.TITLES
    title_aliases = re.findall(r"GAME_SALES\.TITLES\s+(?:AS\s+)?(\w+)", sql, _FLAGS)
    title_aliases = [a for a in title_aliases if a.upper() not in ("ON", "JOIN", "WHERE", "LEFT", "INNER", "GROUP")]
    if _has(r"GAME_SALES\.TITLES\.CATALOG_GAME_ID", sql) or any(
        _has(rf"\b{re.escape(a)}\.CATALOG_GAME_ID\b", sql) for a in title_aliases
    ):
        return ("fail", "Linked sales to the catalog with TITLES.CATALOG_GAME_ID, which is NULL for 13 titles; "
                        "the rule is SELECT DISTINCT TITLE_ID, CATALOG_GAME_ID FROM TITLE_CODE_XREF.")
    if _has(r"TITLE_CODE_XREF", sql):
        if _has(r"SELECT\s+DISTINCT\s+(?:\w+\.)?TITLE_ID\s*,\s*(?:\w+\.)?CATALOG_GAME_ID[^)]*TITLE_CODE_XREF", sql):
            return ("pass", "Mapped sales titles to catalog games through SELECT DISTINCT on TITLE_CODE_XREF.")
        return ("fail", "Joined TITLE_CODE_XREF without DISTINCT; it has one row per title and platform, "
                        "so revenue is counted once per title code.")
    return None


def _cumulative_income(sql):
    if _has(r"SUM\s*\(\s*(?:\w+\.)?CUMULATIVE_INCOME", sql):
        return ("fail", "Summed CUMULATIVE_INCOME, a running total; sum MONTHLY_INCOME instead.")
    return None


def _revenue_source_phase(sql):
    if _has(r"REVENUE_SOURCE\s*(?:=|IN\s*\()\s*'?(?:launch|tail|ongoing|seasonal|dlc_bump)'", sql):
        return ("fail", "Filtered REVENUE_SOURCE as a lifecycle phase; it is the monetization type. "
                        "Phases come from months since TITLES.RELEASE_DATE.")
    if _has(r"DATEDIFF\s*\(\s*MONTH", sql) and _has(r"RELEASE_DATE", sql) and _has(r"MONTHLY_REVENUE", sql):
        return ("pass", "Derived lifecycle phases from months since release.")
    return None


def _genre_full_match(sql):
    if not _has(r"GAME_GENRE_CLASSIFICATION", sql):
        return None
    if _has(r"MATCH_STATUS\s*=\s*'FULL'", sql):
        return ("pass", "Used fully matched genres only (MATCH_STATUS = 'FULL').")
    return ("fail", "Used GAME_GENRE_CLASSIFICATION without MATCH_STATUS = 'FULL'; PARTIAL and NONE rows "
                    "are not genre membership.")


def _sum_distinct_income(sql):
    if _has(r"SUM\s*\(\s*DISTINCT\s+(?:\w+\.)?INCOME", sql):
        return ("fail", "Used SUM(DISTINCT income), which merges different titles with equal income; "
                        "dedupe to one row per title first.")
    return None


def _txn_title(sql):
    # Transaction TITLE_ID joined to TITLES (NULL for ~10% of digital revenue).
    txn_aliases = re.findall(r"DIGITAL_PRODUCT_TRANSACTIONS\s+(?:AS\s+)?(\w+)", sql, _FLAGS)
    txn_aliases = [a for a in txn_aliases if a.upper() not in ("ON", "JOIN", "WHERE", "LEFT", "INNER", "GROUP")]
    for a in txn_aliases:
        if _has(rf"=\s*{re.escape(a)}\.TITLE_ID\b", sql) or _has(rf"\b{re.escape(a)}\.TITLE_ID\s*=", sql):
            if _has(r"GAME_SALES\.TITLES\b", sql):
                return ("fail", "Took the title from the transaction's TITLE_ID, which is NULL for about 10% of "
                                "digital revenue; take it from DIGITAL_PRODUCTS.TITLE_ID.")
    if txn_aliases and _has(r"DIGITAL_PRODUCTS", sql) and _has(r"GAME_SALES\.TITLES\b", sql):
        return ("pass", "Took each transaction's title from its product.")
    return None


CHECKS = [
    ("Sales-to-catalog mapping", _sales_to_catalog),
    ("Monthly income, not cumulative", _cumulative_income),
    ("Lifecycle phases from release date", _revenue_source_phase),
    ("Fully matched genres", _genre_full_match),
    ("Income counted once per title", _sum_distinct_income),
    ("Digital title via product", _txn_title),
]


def check_sql(sql):
    if not sql:
        return []
    sql = _norm(sql)
    out = []
    for rule, fn in CHECKS:
        res = fn(sql)
        if res:
            out.append({"rule": rule, "status": res[0], "reason": res[1]})
    return out


def is_exploratory(sql):
    """A schema/data probe (e.g. SELECT * ... LIMIT 3): small LIMIT, no aggregation, GROUP BY or JOIN.
    Its result never feeds the answer, so it can't break a rule."""
    if not sql:
        return False
    sql = _norm(sql)
    m = re.search(r"\bLIMIT\s+(\d+)\s*;?\s*$", sql.strip(), _FLAGS)
    if not m or int(m.group(1)) > 10:
        return False
    return not _has(r"\bGROUP\s+BY\b|\bJOIN\b|\b(?:SUM|COUNT|AVG|MIN|MAX|MEDIAN)\s*\(", sql)


def check_steps(steps):
    """Merge flags across the SQL steps of one answer: a rule fails if any non-exploratory step fails it."""
    merged = {}
    for s in steps:
        if is_exploratory(s.get("sql")):
            continue
        for f in check_sql(s.get("sql")):
            prev = merged.get(f["rule"])
            if prev is None or (prev["status"] == "pass" and f["status"] == "fail"):
                merged[f["rule"]] = f
    return list(merged.values())


if __name__ == "__main__":
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "prime", pathlib.Path(__file__).resolve().parent / "prime_query_history.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    bad = 0
    for label, sql in mod.QUERIES:
        fails = [f for f in check_sql(sql) if f["status"] == "fail"]
        if fails:
            bad += 1
            print(f"FAIL  {label}: {[f['rule'] for f in fails]}")
    print(f"{len(mod.QUERIES) - bad}/{len(mod.QUERIES)} primed queries pass every rule check")
