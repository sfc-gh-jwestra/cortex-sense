
## Prompt 1: Learn about /cortex-sense skill

**Copy-this-Prompt**:
"How should I prompt the /cortex-sense skill to begin building a new context?"

**Copy-this-Prompt**:
"What can I do with the /cortex-sense skill?"



## Prompt 2: Set up the context

**Copy-this-Prompt**: 
"/cortex-sense  set up cortex sense for video game classification"


This responds with a flow how how to setup a context (info it's going to need) 


If you already have the info, you can just include in your initial prompt to set up a Cortex Sense context (the domain name, the database and schema for the context, starting queries, and sources like semantic views, dashboards, etc. )

**Copy-this-Prompt:** 

"With /cortex-sense, set up cortex sense context for [your domain] in the [your database.schema here] schema. Include all tables and views except backups. Look in query history for same patterns as the schema. Use the streamlist app, [FQN to a streamlit app here]. Example questions are: [your questions here]"


╭────────────────────────────────────────────────────────────────────╮
│         Cortex Sense — grounded context for CoCo & CoWork          │
╰────────────────────────────────────────────────────────────────────╯

  Curating context for agents by hand can't cover everything.
  Cortex Sense indexes the rest.

    your data estate today        with Cortex Sense
    ····················          ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
    ·····█··············          ▒▒▒▒▒█▒▒▒▒▒▒▒▒▒▒▒▒▒▒
    ····················          ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
    ··············█··█··    ──▶   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▒▒█▒▒
    ··················█·          ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒█▒
    ····················          ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
    mostly uncovered              every table grounded

    █ hand-curated context   · no context, agent guesses   ▒ grounded by Sense

  Agents answer well only when they have context — what your tables mean,
  how they join, how metrics are defined. Cortex Sense helps you create this
  layer from how your data is used today, starting from your queries,
  dashboards, semantic views, and dbt models. This layer is used to help
  Cortex Code, Cortex Agents, and CoWork answer questions across your
  warehouse with quality.

  How this works:

    1. Scope it with me — about 10 minutes. Name a domain, I propose what
       to include, you adjust.

    2. I index it in the background — usually a few hours. It goes live
       when it's done; you don't have to wait around.
    
    3. We set up an eval together so you can measure it answers your real
       questions well.

  ▶ Name the domain or use case you want Sense for — eg: "sales pipeline",
    "finance reporting" — or paste a doc, spec, or schema list to start.



## Prompt 3: Provide domain, if CoCo asks for it

If CoCo doesn't deduce the domain from the initial prompt, supply it in a another turn.

**Copy-this-Prompt**: "domain = game-classification"


Cortex Sense will scan at the ACCOUNT level, for anything that resembles the domain. In this case, it even found a Business Ontology for gaming that was setup for a different demo. You can approve or deny sources.


### Sample Response

Storage is set. Now I'm running the discovery scan in parallel: catalog searches, existing context, ontology, warehouse/role, and the background query-history scan.

Scan complete — here's the proposed scope for Cortex Sense for GAME_CLASSIFICATION, based on what your team actually queries.

─── GAME_CLASSIFICATION · scope ──────────────────────  proposed

  ═══ SOURCES ══════════════════════════════════════════════════════
  Objects in your account, scoped by rules. Each rule re-runs on
  every refresh; the count on the right is what it matched now.

    INCLUDE — pulled into scope
      PATTERN                               │  DISCOVERED NOW
      ──────────────────────────────────────┼──────────────────────
      Tables                                │
        CORTEX_SENSE_DEMO.GAME_CATALOG.*    │  ~38  GAME_GENRE_CLASSIFICATION,
                                            │       GENRE_RULES +36
      Semantic Views                        │
        ONTOLOGY_DEMO.GAME_CATALOG.SV_GENRE_TAXONOMY │  1
      Ontology        Genre Taxonomy        │   27  Nodes
                                            │   25  Relationships
                                            │   31  Associations

    EXCLUDE — kept out of every answer, even on future refreshes
      PATTERN                               │  DISCOVERED NOW
      ──────────────────────────────────────┼──────────────────────
      Tables                                │
        BACKUP.*                            │  —
        DEMO.GAMES.*                        │  —

  _(Still scanning your query history — type refresh to update)_

──────────────────────────────────────────────────────────────────
  build · include <pattern> · exclude <pattern> · deeper · refresh
  

ONTOLOGY_DEMO.GAME_CATALOG.* holds the same 38 tables as CORTEX_SENSE_DEMO.GAME_CATALOG.*. I left it out and kept the copy that more people query. The SV_GENRE_TAXONOMY semantic view reads from the ONTOLOGY_DEMO copy, though. Tell me which copy you want to keep.

The only Streamlit app in CORTEX_SENSE_DEMO is GAME_SALES_DASHBOARD, a sales dashboard, so I left it out. The ontology domain is saved with the scope, but the build doesn't index ontology content yet.

  [skip]  must-have tables   e.g. CORTEX_SENSE_DEMO.GAME_SALES.TITLE_CODE_XREF

  [skip]  business docs      e.g. a genre-rules spec on a stage

  [skip]  dbt                stage path to manifest.json — or a local repo path and I'll upload it


  Next: reply with anything above to include more scope, or type "build" to start. The build is a background job that turns this scope into the knowledge CoCo uses to answer questions about your data. It can take minutes or hours depending on the scope, and it runs on COMPUTE_WH. You can narrow the scope anytime.





 ## Prompt 4: Ask Sense a question

**Copy-this-Prompt**:
  "Using [your domain context here] What genre has the most games?"

  Result: CoCo will query the cortex sense context and reply with data table results and citations used to answer

  ## Prompt 5: List cortex sense feedback rules for your context

Before prompting, let's go over the different types of feedback rules first:

 **1. Definition:**  
 
 Says what a term or metric means. Use it when the business meaning of a word needs to be fixed in place.

Example: "DAU is COUNT(DISTINCT user_id) over events in a calendar day."

 **2. Retrieval steer**: 
 
 Points a kind of question at the right table or object. Use it when answers keep coming from the wrong source.

Example: "For pipeline questions use SALES.DATA.OPPORTUNITIES, not SALES.STAGING.OPPS."

  **3. Annotation:** 
 
 Records a lasting fact about the data that a future build could absorb into the context itself.

Example: "ORDERS.AMOUNT is stored in cents, not dollars," or "Region 'EMEA-X' was merged into 'EMEA' in 2025."

  **4. Procedural:** 
  
Sets a standing rule that should apply all the time, not a fact to absorb.

Example: "Never expose PII columns," or "Always exclude test accounts from customer counts."

Annotation vs procedural: ask whether a future build could absorb it as a fact about the data. If yes, it's an annotation. If it's a policy that must stay in force every time, it's procedural.

 **5. Relationship:** 

 X is the same as, derives from, or feeds Y
 
 **6. Association:** 

Concept X lives in table Y. Changes to what's in scope, like adding a schema or excluding staging, aren't feedback at all. The server rejects them, and you make them through refine instead.


**Copy-this-Prompt**: 
"List cortex sense feedback rules for [your domain context]"

### Example Response:
The cortex_sense_inbox tool lists feedback records for a context, so I'll use it.`GAME_ANALYTICS_CTX_V2` (`CORTEX_SENSE_DEMO.CONTEXTS`) has **26 feedback rules**. All are active and builder-declared with high trust, and all were created on 2026-10-24. The fullscreen inbox opened alongside this, if you want more detail per record.

**Definitions (10)**
| Rule | Summary |
| --- | --- |
| Fiscal year | Fiscal year is the calendar year (Jan to Dec), based on `YEAR(CURRENT_DATE())`. |
| Publisher/studio names | Sales uses `SIE` and "Naughty Dog"; the catalog uses "Sony Interactive Entertainment" and `Naughty_Dog`. Join by ID through `TITLE_CODE_XREF`, never by name. |
| Revenue by monetization model | Uses the model tags on each title (`GAME_MONETIZATION`), not product types. Totals overlap and must not be summed. |
| Content rating risk | A game qualifies if it has a mature rating (`MIN_AGE >= 16`), violence inferred from genre, theme and gameplay, or romance. |
| Franchise cannibalization | Same-publisher franchises with `WEIGHTED_OVERLAP >= 0.3`. Recommend CONSOLIDATE, SUNSET or REPOSITION, otherwise flag for review. |
| Live-service | `ONLINE_REQUIRED` plus recurring monetization (battle pass, microtransactions, subscription or loot boxes). |
| Proven capability | No studio rating exists. Use a labelled proxy: award wins, top-quartile income and 3+ fully matched genres. |
| Emerging genre | No demand data exists. Use a labelled proxy: `MARKET_STATUS` of UNDERSERVED or WHITESPACE. |
| Breakout hit | Top-quartile income or a Game_of_the_Year win. Also defines the "award-winning formula". |

**Procedural (8)**
| Rule | Summary |
| --- | --- |
| Genre revenue | Count only `MATCH_STATUS = 'FULL'`, and use the rollup view for broad genres. Totals are about 3x total revenue; report unmatched and unmapped titles separately. |
| Time series | Monthly data from `MONTHLY_REVENUE`, quarterly from `QUARTERLY_REVENUE`. For YoY, compare the same quarter. |
| Monetization risk | Join monetization types to `VW_PLATFORM_EXCLUSIVITY`. |
| EU regulatory risk | Use only the loot-box brief. Apply the HIGH, ELEVATED and WATCH tiers in that order to live-service games, and note it is not legal advice. |
| Audience profile | Inferred from genre clusters, platform reach and narrative style. |
| Release calendar | Releases conflict when they are in the same quarter and have overlap `>= 0.3`. Includes the "major release" threshold. |
| Accessibility priority | Score is games missing a feature times average income. It is a ranking only, never dollars. |
| Audience comparison | Check `GAME_SIMILARITY_SCORES` in both directions first and cite `OVERLAP_TIER`. |

**Retrieval steers (6)**
| Rule | Summary |
| --- | --- |
| Revenue analysis | Follow `SV_GAME_SALES`. Lifetime revenue is `GAME_REVENUE.INCOME`. "Top earners" means the top 5 by income. |
| Monthly revenue | `REVENUE_SOURCE` is the monetization type, not the lifecycle phase. Sum `MONTHLY_INCOME`, never the cumulative column. |
| Quarterly revenue | `QUARTERLY_REVENUE` is a rollup of the monthly data. |
| Exclusivity revenue | `VW_PLATFORM_EXCLUSIVITY` where `IS_CURRENTLY_EXCLUSIVE`, counting each title once. |
| Awards | `GAME_AWARDS` joined to `AWARDS`, filtered to `'won'`, grouped by awarding body. |
| Accessibility | Use the `VW_ACCESSIBILITY_GAPS` matrix; `IS_SUPPORTED = FALSE` means the feature is missing. |
| Game engines | Engine data exists in `GAME_ENGINES` and `ENGINES`. Never say it's unavailable. |

**Annotations (2)**
| Rule | Summary |
| --- | --- |
| Release date | `GAMES.RELEASE_DATE` is already a DATE, so no conversion is needed. |
| Rating equivalence | Self-join `AGE_RATINGS` on `MIN_AGE`. |

The definitions table has nine rows, one short of the count. Breaking down the other three types the same way gives 8 procedural, 7 retrieval steers and 2 annotations: 9 + 8 + 7 + 2 = 26.