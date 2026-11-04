# Lab 3: Evaluate and Improve the Context

## Overview

In Lab 2 you built the `pawprime-sales` context and asked it questions. Some answers were right; others counted cancelled orders as sales. In this lab you **measure** answer quality with an eval set, **fix** what's wrong with feedback rules, and **prove** the fix by re-running the eval.

You will:

0. Review pending items from setup
1. Generate an eval set from your example questions
2. Run a baseline eval
3. Add feedback rules
4. Verify the rules are in the context
5. Re-run the eval and compare the runs
6. Spot-check the fix in CoCo

### Prerequisites

- Lab 2 completed, and the build reports it is done:

  **Copy-this-Prompt:**

  > What is the build status of the pawprime-sales cortex sense context?

- The Food total you wrote down in Lab 2 Step 3

All prompts below are typed into the CoCo chat panel.

## Step 0: Review pending items from setup

**Refine** is how you change an existing Cortex Sense context after it's built. It reopens the scope card from the saved context (not a fresh scan) and lets you edit it in plain English: add or exclude schemas, change the warehouse, answer anything left open from setup. When you type `done`, CoCo saves a new version of the scope and queues a rebuild. Business rules (definitions, policies) go through feedback in Step 3, not refine.

During setup, CoCo saved two **pending items**: things it couldn't settle at the time.

- **Your 5 example questions.** These are input for the eval set in Step 1.
- **Business docs.** An optional stage path to a metrics spec (for example net sales or gross margin definitions).

Open the context in refine to see them:

**Copy-this-Prompt:**

> $cortex-sense resume pawprime-sales — refine

CoCo shows the saved scope card. The pending items appear in its **Optional** section. Clear the docs item and close refine:

**Copy-this-Prompt:**

> skip business docs

**Copy-this-Prompt:**

> done

If you have a real metrics doc on a stage, give its path instead of skipping it, for example `business docs at @CORTEX_SENSE_DEMO.WORKSHOP.SENSE_SOURCES/metrics.md`.

> **You can skip this step.** Leaving the pending items open is harmless. They don't affect answers, and the example questions are picked up by `generate eval` in Step 1 either way. This step is here so you see how refine works.

## Step 1: Generate the eval set

An eval set is a list of business questions, each with a confirmed **expected answer**. The skill starts from the five example questions you gave at setup and can propose more from the context.

**Copy-this-Prompt:**

> $cortex-sense resume pawprime-sales — generate eval

CoCo asks where questions should come from (use the setup questions, the context, or both), then proposes an expected answer for each and shows them in a review table. For each question:

- **Accept** it if the expected answer is right
- **Correct** it: `update golden q<n> "<answer>"`
- **Drop** it: `reject q<n>`

Make sure the expected answers follow PawPrime's business rules. For example, net sales **excludes** orders where `ORDER_STATUS = 'Cancelled'`, and revenue is `SUM(ORDER_ITEM.LINE_TOTAL)`. Every question needs a confirmed expected answer before it can be scored.

## Step 2: Run the baseline eval

**Copy-this-Prompt:**

> run eval

The eval scores a live Cortex Sense agent against your confirmed questions using Snowflake's native Cortex Agent Evaluations. If you don't have an agent over `PAWPRIME_SALES` yet, CoCo walks you through creating one. Confirm the agent spec when asked.

When the run finishes, CoCo shows a score per question and a Snowsight link where you can see each produced answer and the judge's reasoning.

Expect the net sales and category questions to score low. The context doesn't yet know that cancelled orders are excluded. Write down the scores so you can compare them in Step 5.

## Step 3: Add feedback rules

Feedback rules are standing instructions the context applies on top of what it learned from the build. There are six types:

| Type | Use it for | Example |
|---|---|---|
| Definition | What a term or metric means | "Gross margin is LINE_TOTAL - QUANTITY * UNIT_COST." |
| Retrieval steer | Pointing a kind of question at the right object | "For sales questions use SV_PET_STORE." |
| Annotation | A lasting fact about the data | "UNIT_PRICE on ORDER_ITEM is the price paid, not list price." |
| Procedural | A policy that must apply every time | "Always exclude cancelled orders from sales." |
| Relationship | X is the same as, derives from, or feeds Y | "LINE_TOTAL = QUANTITY * UNIT_PRICE." |
| Association | Concept X lives in table Y | "Autoship enrollment lives in CUSTOMER.IS_AUTOSHIP." |

See [learning-how-to-use-sense-skill.md](learning-how-to-use-sense-skill.md) for more on each type. Scope changes (adding a schema, excluding objects) are not feedback; make those through the scope card instead.

PawPrime's finance team says "sales" always means **net sales**, which exclude cancelled orders. That's a policy that should hold every time, so it's a procedural rule.

**Copy-this-Prompt:**

> With /cortex-sense, record feedback for the pawprime-sales context: sales and revenue always mean net sales, which exclude orders where ORDERS.ORDER_STATUS = 'Cancelled'. Revenue is SUM(ORDER_ITEM.LINE_TOTAL), never a sum of ORDERS columns.

> **Tip:** you can also start from a failing question. Type `refine q<n>` and CoCo loads that question and its expected answer as the starting point for the correction.

CoCo submits the rule and confirms its type. A new rule is queued for builder review (state `needs_feedback`) before it takes effect. If you own the context, approve it:

**Copy-this-Prompt:**

> Approve the net sales feedback rule for the pawprime-sales context.

**Optional:** add a definition rule as well.

> With /cortex-sense, record feedback for the pawprime-sales context: gross margin is ORDER_ITEM.LINE_TOTAL minus ORDER_ITEM.QUANTITY * PRODUCT.UNIT_COST, and gross margin % is gross margin divided by LINE_TOTAL.

## Step 4: Verify the rules are in the context

**Copy-this-Prompt:**

> List my feedback rules for the pawprime-sales context

CoCo opens the feedback inbox and summarizes the rules. Expect something like:

| Type | Rule | State |
|---|---|---|
| Procedural | Sales and revenue mean net sales; exclude `ORDER_STATUS = 'Cancelled'`. Revenue is `SUM(ORDER_ITEM.LINE_TOTAL)`. | active |
| Definition | Gross margin is `LINE_TOTAL - QUANTITY * UNIT_COST`; margin % divides by `LINE_TOTAL`. | active |

If a rule still shows `needs_feedback`, it hasn't been approved yet; go back to Step 3.

## Step 5: Re-run the eval and compare

Run the same questions again:

**Copy-this-Prompt:**

> run eval

Then compare the two runs:

**Copy-this-Prompt:**

> diff eval

CoCo lists which questions improved, which regressed, and which stayed the same. The net sales and category questions (and gross margin, if you added the optional rule) should improve, and nothing else should regress.

If a question still fails, open its Snowsight link, see what went wrong, and record another rule the same way as in Step 3. Then re-run.

## Step 6: Spot-check in CoCo

Ask the Lab 2 baseline question again:

**Copy-this-Prompt:**

> Using the pawprime-sales context, what were total sales by product category?

The SQL should now include `ORDER_STATUS <> 'Cancelled'`, and the Food total should be lower than the one you wrote down in Lab 2. CoCo ends the answer with a Cortex Sense citation line and names the objects it used.

## Cleanup

The context, eval files, and feedback rules live in `CORTEX_SENSE_DEMO.WORKSHOP`, so the Lab 1 teardown removes them along with the tables and semantic view. If you created a Cortex Agent in Step 2 outside that schema, drop it separately.

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN -f intro-workshop/sql/99_teardown.sql
```
