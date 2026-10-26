CREATE OR REPLACE PROCEDURE CORTEX_SENSE_DEMO.GAME_CATALOG.SP_CLASSIFY_GAMES()
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run'
EXECUTE AS OWNER
AS '
import json
import re

def run(session):
    def parse_array(val):
        if val is None:
            return set()
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                return set(v for v in parsed if v is not None)
            except:
                return set()
        if isinstance(val, list):
            return set(v for v in val if v is not None)
        return set()

    rules_df = session.sql("SELECT GENRE, RULE_DEFINITION FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_RULES WHERE RULE_DEFINITION IS NOT NULL").collect()
    rules = [(r[''GENRE''], r[''RULE_DEFINITION'']) for r in rules_df]

    cat_df = session.sql("SELECT CATEGORY_NAME, PREDICATE_TYPE, CONCRETE_VALUE FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GENRE_CATEGORY_MAP").collect()
    categories = {}
    for row in cat_df:
        key = (row[''PREDICATE_TYPE''], row[''CATEGORY_NAME''])
        categories.setdefault(key, set()).add(row[''CONCRETE_VALUE''])

    profiles_df = session.sql("""
        SELECT GAME_ID, GAME_NAME, POV, NARRATIVE,
                GAMEPLAY_TYPES, MECHANICS, CONTEXTS,
                MAX_PLAYER_COUNT, HAS_ONLINE_MODE
        FROM CORTEX_SENSE_DEMO.GAME_CATALOG.VW_GAME_PROFILE
    """).collect()

    mon_df = session.sql("""
        SELECT g.GAME_ID, ARRAY_AGG(DISTINCT mt.MONETIZATION_NAME) AS MONETIZATION_TYPES
        FROM CORTEX_SENSE_DEMO.GAME_CATALOG.GAMES g
        LEFT JOIN CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_MONETIZATION gm ON g.GAME_ID = gm.GAME_ID
        LEFT JOIN CORTEX_SENSE_DEMO.GAME_CATALOG.MONETIZATION_TYPES mt ON gm.MONETIZATION_ID = mt.MONETIZATION_ID
        GROUP BY g.GAME_ID
    """).collect()
    monetization_map = {}
    for row in mon_df:
        monetization_map[row[''GAME_ID'']] = parse_array(row[''MONETIZATION_TYPES''])

    games = []
    for row in profiles_df:
        games.append({
            ''game_id'': row[''GAME_ID''],
            ''game_name'': row[''GAME_NAME''],
            ''pov'': row[''POV''] if row[''POV''] else '''',
            ''narrative'': row[''NARRATIVE''] if row[''NARRATIVE''] else '''',
            ''gameplay'': parse_array(row[''GAMEPLAY_TYPES'']),
            ''mechanic'': parse_array(row[''MECHANICS'']),
            ''context'': parse_array(row[''CONTEXTS'']),
            ''max_players'': row[''MAX_PLAYER_COUNT''],
            ''online'': row[''HAS_ONLINE_MODE''],
            ''monetization'': monetization_map.get(row[''GAME_ID''], set())
        })

    UNEVALUABLE_PREDICATES = {''hasDifficulty'', ''hasUpdate''}

    def parse_conditions(rule_def):
        if not rule_def or not rule_def.strip():
            return []
        rule_def = rule_def.strip()
        if rule_def.startswith(''INTERSECTION('') and rule_def.endswith('')''):
            inner = rule_def[13:-1]
            conditions = []
            depth = 0
            current = ''''
            for ch in inner:
                if ch in (''('', ''{''):
                    depth += 1
                    current += ch
                elif ch in ('')'', ''}''):
                    depth -= 1
                    current += ch
                elif ch == '','' and depth == 0:
                    conditions.append(current.strip())
                    current = ''''
                else:
                    current += ch
            if current.strip():
                conditions.append(current.strip())
            return conditions
        else:
            return [rule_def]

    def evaluate_condition(cond, game, categories):
        cond = cond.strip()
        if cond.startswith(''NOT('') and cond.endswith('')''):
            inner_cond = cond[4:-1]
            if inner_cond == ''requiresOnline'':
                if game[''online''] is None:
                    return (''UNKNOWN'', ''requiresOnline: no mode data'')
                return (''MET'', ''NOT online'') if not game[''online''] else (''MISSING'', ''game requires online'')
            result, detail = evaluate_condition(inner_cond, game, categories)
            if result == ''MET'':
                return (''MISSING'', f''NOT failed: {detail}'')
            elif result == ''MISSING'':
                return (''MET'', f''NOT passed: {detail}'')
            else:
                return (''UNKNOWN'', f''NOT unknown: {detail}'')

        m = re.match(r''(has\\w+|requiresOnline)\\s+(SOME|VALUE|MIN|MAX)\\s+(.*)'', cond)
        if not m:
            return (''UNKNOWN'', f''unparseable: {cond}'')

        predicate, operator, operand = m.group(1), m.group(2), m.group(3).strip()

        if predicate in UNEVALUABLE_PREDICATES:
            return (''UNKNOWN'', f''{predicate}: no data available'')

        prop_map = {
            ''hasGameplay'': (''gameplay'', ''array''),
            ''hasMechanic'': (''mechanic'', ''array''),
            ''hasContext'': (''context'', ''array''),
            ''hasPOV'': (''pov'', ''scalar''),
            ''hasNarrative'': (''narrative'', ''scalar''),
            ''hasPlayerCount'': (''max_players'', ''numeric''),
            ''requiresOnline'': (''online'', ''boolean''),
            ''hasMonetization'': (''monetization'', ''array''),
        }

        if predicate not in prop_map:
            return (''UNKNOWN'', f''unknown predicate: {predicate}'')

        prop_key, prop_type = prop_map[predicate]
        game_val = game[prop_key]

        if operator == ''VALUE'':
            if prop_type == ''array'':
                if not game_val:
                    return (''UNKNOWN'', f''{predicate}: no data'')
                if operand in game_val:
                    return (''MET'', f''{predicate}={operand}'')
                return (''MISSING'', f''{predicate} missing {operand}'')
            elif prop_type == ''scalar'':
                if game_val == operand:
                    return (''MET'', f''{predicate}={operand}'')
                return (''MISSING'', f''{predicate}={game_val} needs {operand}'')
            elif prop_type == ''boolean'':
                expected = operand.lower() == ''true''
                if game_val is None:
                    return (''UNKNOWN'', f''{predicate}: no data'')
                if game_val == expected:
                    return (''MET'', f''{predicate}={operand}'')
                return (''MISSING'', f''{predicate}={game_val} needs {operand}'')

        elif operator == ''SOME'':
            if operand.startswith(''{'') and operand.endswith(''}''):
                values = set(v.strip() for v in operand[1:-1].split('',''))
                if prop_type == ''array'':
                    if not game_val:
                        return (''UNKNOWN'', f''{predicate}: no data'')
                    overlap = game_val & values
                    if overlap:
                        return (''MET'', f''{predicate} has {overlap}'')
                    return (''MISSING'', f''{predicate} needs one of {values}'')
                elif prop_type == ''scalar'':
                    if game_val in values:
                        return (''MET'', f''{predicate}={game_val}'')
                    return (''MISSING'', f''{predicate}={game_val} not in {values}'')
            else:
                cat_key = (prop_key, operand)
                concrete = categories.get(cat_key, set())
                if not concrete:
                    return (''UNKNOWN'', f''no category mapping: {prop_key}/{operand}'')
                if prop_type == ''array'':
                    if not game_val:
                        return (''UNKNOWN'', f''{predicate}: no data'')
                    overlap = game_val & concrete
                    if overlap:
                        return (''MET'', f''{predicate} SOME {operand}: {overlap}'')
                    return (''MISSING'', f''{predicate} SOME {operand}: none of {concrete}'')
                elif prop_type == ''scalar'':
                    if game_val in concrete:
                        return (''MET'', f''{predicate} SOME {operand}: {game_val}'')
                    return (''MISSING'', f''{predicate} SOME {operand}: {game_val} not in {concrete}'')

        elif operator == ''MIN'':
            threshold = int(operand)
            if game_val is None:
                return (''UNKNOWN'', f''{predicate}: no player count'')
            if game_val >= threshold:
                return (''MET'', f''players={game_val}>={threshold}'')
            return (''MISSING'', f''players={game_val}<{threshold}'')

        elif operator == ''MAX'':
            threshold = int(operand)
            if game_val is None:
                return (''UNKNOWN'', f''{predicate}: no player count'')
            if game_val <= threshold:
                return (''MET'', f''players={game_val}<={threshold}'')
            return (''MISSING'', f''players={game_val}>{threshold}'')

        return (''UNKNOWN'', f''unhandled: {cond}'')

    results = []
    for game in games:
        for genre, rule_def in rules:
            conditions = parse_conditions(rule_def)
            if not conditions:
                continue

            met, missing, unknown = [], [], []
            for cond in conditions:
                status, detail = evaluate_condition(cond, game, categories)
                if status == ''MET'':
                    met.append(detail)
                elif status == ''MISSING'':
                    missing.append(detail)
                else:
                    unknown.append(detail)

            total = len(conditions)
            met_count = len(met)
            score = met_count / max(total, 1)

            if unknown and not missing and met_count + len(unknown) == total:
                match_status = ''UNEVALUABLE'' if met_count == 0 else ''PARTIAL''
            elif met_count == total:
                match_status = ''FULL''
            elif met_count > 0:
                match_status = ''PARTIAL''
            else:
                match_status = ''NONE''

            results.append((
                game[''game_id''], game[''game_name''], genre, match_status,
                round(score, 4), total, met_count,
                json.dumps(met), json.dumps(missing), json.dumps(unknown)
            ))

    session.sql("TRUNCATE TABLE CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION").collect()

    batch_size = 100
    for i in range(0, len(results), batch_size):
        batch = results[i:i+batch_size]
        selects = []
        for r in batch:
            gid, gn, ge, ms, sc, tot, mc, ma, mi, uk = r
            gn = gn.replace("''", "''''") if gn else ''''
            ge = ge.replace("''", "''''")
            ma = ma.replace("''", "''''")
            mi = mi.replace("''", "''''")
            uk = uk.replace("''", "''''")
            selects.append(
                f"SELECT {gid}, ''{gn}'', ''{ge}'', ''{ms}'', "
                f"{sc}, {tot}, {mc}, "
                f"PARSE_JSON(''{ma}''), PARSE_JSON(''{mi}''), PARSE_JSON(''{uk}'')"
            )
        sql = f"""INSERT INTO CORTEX_SENSE_DEMO.GAME_CATALOG.GAME_GENRE_CLASSIFICATION
            (GAME_ID, GAME_NAME, GENRE, MATCH_STATUS, MATCH_SCORE, TOTAL_CONDITIONS, MET_CONDITIONS, MATCHED_CONDITIONS, MISSING_CONDITIONS, UNKNOWN_CONDITIONS)
            {'' UNION ALL ''.join(selects)}"""
        session.sql(sql).collect()

    return f''Classified {len(games)} games against {len(rules)} rules. {len(results)} evaluations.''
';
