# Lab 3: Evaluate and Improve the Context

## Overview

In Lab 2 you built the `pawprime-sales` context and asked it questions. The context correctly excluded cancelled orders (it learned that from the semantic view), but it counted returned orders as sales, which PawPrime finance doesn't allow. In this lab you **measure** answer quality with an eval set, **fix** what's wrong with feedback rules, and **prove** the fix by re-running the eval.

You will:

1. Review pending items from setup
2. Create a Cortex Agent for the context
3. Generate an eval set from your example questions
4. Run a baseline eval
5. Add feedback rules
6. Verify the rules are in the context
7. Re-run the eval and compare the runs
8. Spot-check the fix in CoCo

### Prerequisites

- Lab 2 completed, and the build reports it is done:

  **Copy-this-Prompt:**

  > What is the build status of the pawprime-sales cortex sense context?

- The Food total you wrote down in Lab 2 Step 3

All prompts below are typed into the CoCo chat panel.

## Step 1: Review pending items from setup

**Refine** is how you change an existing Cortex Sense context after it's built. It reopens the scope card from the saved context (not a fresh scan) and lets you edit it in plain English: add or exclude schemas, change the warehouse, answer anything left open from setup. When you type `done`, CoCo saves a new version of the scope and queues a rebuild. Business rules (definitions, policies) go through feedback in Step 5, not refine.

During setup, CoCo saved two **pending items**: things it couldn't settle at the time.

- **Your 5 example questions.** These are input for the eval set in Step 3.
- **Business docs.** An optional stage path to a metrics spec (for example net sales or gross margin definitions).

Open the context in refine to see them:

**Copy-this-Prompt:**

> $cortex-sense resume pawprime-sales — refine

CoCo shows the saved scope card. The pending items appear in its **Optional** section. Clear the docs item and close refine:

**Copy-this-Prompt:**

> skip business docs

**Copy-this-Prompt:**

> done

> **You can skip this step.** Leaving the pending items open is harmless. They don't affect answers, and the example questions are picked up by `generate eval` in Step 3 either way. This step is here so you see how refine works.

## Step 2: Create a Cortex Agent for the context

The eval scores a live **Cortex Agent** that answers questions using the `pawprime-sales` context. Create the agent now so it's ready for the baseline run.

**Copy-this-Prompt:**

> With /cortex-sense, set up an agent for the pawprime-sales context. Create it in the CORTEX_SENSE_DEMO.WORKSHOP schema.

CoCo proposes an agent spec: the agent name, where it's stored, the context it reads from (`PAWPRIME_SALES`) and the warehouse it runs on. Review the spec and confirm it when asked.

When it finishes, CoCo shows the agent's fully qualified name. Write it down; the eval in Step 4 runs against it.

> **Why store it in `CORTEX_SENSE_DEMO.WORKSHOP`?** The Lab 1 teardown drops that schema, so the agent is cleaned up along with everything else.

## Step 3: Generate the eval set

An eval set is a list of business questions, each with a confirmed **expected answer**. The skill starts from the five example questions you gave at setup and can propose more from the context.

**Copy-this-Prompt:**

> $cortex-sense resume pawprime-sales — generate eval

CoCo asks where questions should come from (use the setup questions, the context, or both), then proposes an expected answer for each and shows them in a review table. For each question:

- **Accept** it if the expected answer is right
- **Correct** it: `update golden q<n> "<answer>"`
- **Drop** it: `reject q<n>`

Make sure the expected answers follow PawPrime's business rules. Net sales **excludes** both cancelled and returned orders (`ORDER_STATUS NOT IN ('Cancelled', 'Returned')`), and revenue is `SUM(ORDER_ITEM.LINE_TOTAL)`. If a proposed expected answer only excludes cancelled orders, correct it with `update golden q<n>`; otherwise the baseline will score as correct and there's nothing to fix. Every question needs a confirmed expected answer before it can be scored.

## Step 4: Run the baseline eval

**Copy-this-Prompt:**

> run eval

The eval scores the agent you created in Step 2 against your confirmed questions using Snowflake's native Cortex Agent Evaluations. If CoCo asks which agent to use, pick that one.

When the run finishes, CoCo shows a score per question and a Snowsight link where you can see each produced answer and the judge's reasoning.

Expect the net sales and category questions to score low. The context excludes cancelled orders but still counts returned orders as sales. Write down the scores so you can compare them in Step 7.

The /cortex-sense skill will build an evaluation data set in the CORTEX_SENSE_DEMO.WORKSHOP schema.

When/If you are prompted for a Metric Version (ver) Choose v3_0. 
And use only built-in metrics, not a custom LLM-as-a-Judge.

To learn more about how agent evaluations work, including the built-in metrics (answer correctness, logical consistency, tool selection and execution accuracy), dataset format, and custom metrics, see the Snowflake documentation: [Cortex Agent evaluations](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-evaluations).

## Step 5: Add feedback rules

Feedback rules are standing instructions the context applies on top of what it learned from the build. There are six types:

| Type | Use it for | Example |
|---|---|---|
| Definition | What a term or metric means | "Gross margin is LINE_TOTAL - QUANTITY * UNIT_COST." |
| Retrieval steer | Pointing a kind of question at the right object | "For sales questions use SV_PET_STORE." |
| Annotation | A lasting fact about the data | "UNIT_PRICE on ORDER_ITEM is the price paid, not list price." |
| Procedural | A policy that must apply every time | "Always exclude cancelled orders from sales." |
| Relationship | X is the same as, derives from, or feeds Y | "LINE_TOTAL = QUANTITY * UNIT_PRICE." |
| Association | Concept X lives in table Y | "Autoship enrollment lives in CUSTOMER.IS_AUTOSHIP." |

Scope changes (adding a schema, excluding objects) are not feedback; make those through the scope card instead.

PawPrime's finance team says "sales" always means **net sales**, which exclude both cancelled and returned orders. Nothing in the data says returns are excluded, so the context can only learn it from you. That's a policy that should hold every time, so it's a procedural rule.

**Copy-this-Prompt:**

> With /cortex-sense, record feedback for the pawprime-sales context: PawPrime net sales excludes both Cancelled and Returned orders (ORDERS.ORDER_STATUS NOT IN ('Cancelled', 'Returned')). Sales and revenue always mean net sales, computed as SUM(ORDER_ITEM.LINE_TOTAL), never a sum of ORDERS columns.

> **Tip:** you can also start from a failing question. Type `refine q<n>` and CoCo loads that question and its expected answer as the starting point for the correction.

CoCo submits the rule and confirms its type. A new rule is queued for builder review (state `needs_feedback`) before it takes effect. 

CoCo may ask you if it 'looks right' or if you want to edit the rule further. If you opt for 'looks right', it will approve and store it.

If CoCo did not prompt this way and you own the context, approve it now:

**Copy-this-Prompt:**

> Approve the net sales feedback rule for the pawprime-sales context.

**Optional:** add a definition rule as well.

> With /cortex-sense, record feedback for the pawprime-sales context: gross margin is ORDER_ITEM.LINE_TOTAL minus ORDER_ITEM.QUANTITY * PRODUCT.UNIT_COST, and gross margin % is gross margin divided by LINE_TOTAL.

## Step 6: Verify the rules are in the context

**Copy-this-Prompt:**

> List my feedback rules for the pawprime-sales context

CoCo opens the feedback inbox and summarizes the rules. Expect something like:

| Type | Rule | State |
|---|---|---|
| Procedural | Sales and revenue mean net sales; exclude `ORDER_STATUS IN ('Cancelled', 'Returned')`. Revenue is `SUM(ORDER_ITEM.LINE_TOTAL)`. | active |
| Definition | Gross margin is `LINE_TOTAL - QUANTITY * UNIT_COST`; margin % divides by `LINE_TOTAL`. | active |

If a rule still shows `needs_feedback`, it hasn't been approved yet; go back to Step 5.

## Step 7: Re-run the eval and compare

Run the same questions again:

**Copy-this-Prompt:**

> run eval

Then compare the two runs:

**Copy-this-Prompt:**

> diff eval

CoCo lists which questions improved, which regressed, and which stayed the same. The net sales and category questions (and gross margin, if you added the optional rule) should improve, and nothing else should regress.

If a question still fails, open its Snowsight link, see what went wrong, and record another rule the same way as in Step 5. Then re-run.

## Step 8: Spot-check in CoCo

Ask the Lab 2 baseline question again:

**Copy-this-Prompt:**

> Using the pawprime-sales context, what were total sales by product category?

The SQL should now include `ORDER_STATUS NOT IN ('Cancelled', 'Returned')`, and the Food total should drop from about $60,263 (Lab 2) to about $57,806. CoCo ends the answer with a Cortex Sense citation line and names the objects it used.

## Cleanup

The context, Cortex Agent, eval files, and feedback rules live in `CORTEX_SENSE_DEMO.WORKSHOP`, so the Lab 1 teardown removes them along with the tables and semantic view. If you created the agent in Step 2 outside that schema, drop it separately.

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN -f intro-workshop/sql/99_teardown.sql
```
