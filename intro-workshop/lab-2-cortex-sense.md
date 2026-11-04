# Lab 2: Build a Cortex Sense Context

## Overview

In Lab 1 you built the PawPrime tables, the `SV_PET_STORE` semantic view, and a query history that shows how analysts really use the data. In this lab you turn all of that into a **Cortex Sense context**: a grounded knowledge layer that tells CoCo what the tables mean, how they join, and how metrics are defined.

You will:

1. Create a `pawprime-sales` domain with the `/cortex-sense` skill
2. Build the index
3. Ask a baseline question
4. Ask more questions in CoCo using the context

In Lab 3 you'll measure these answers with an eval and fix what's wrong with feedback rules.

Everything, including the context itself, is stored in `CORTEX_SENSE_DEMO.WORKSHOP`, so the Lab 1 teardown removes it all.

### Prerequisites

- Lab 1 completed, including Step 3 (prime the query history). Query history in `ACCOUNT_USAGE` can lag by a few hours, so the scan finds more patterns the longer it has been since you ran the primer.
- Cortex Code (CoCo) connected to the same account and role you used in Lab 1
- A warehouse the build can run on

All prompts below are typed into the CoCo chat panel.

## Step 1: Create the `pawprime-sales` domain

Give the skill everything it needs in one prompt: the domain name, where to store the context, the semantic view, and sample questions.

**Copy-this-Prompt:**

> /cortex-sense set up a cortex sense context for the domain pawprime-sales. Store the context in the CORTEX_SENSE_DEMO.WORKSHOP schema. Scope it to the tables in CORTEX_SENSE_DEMO.WORKSHOP and use the semantic view CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE. Look in query history for the same patterns as the schema. Example questions are: What were net sales last month? Which product categories have the highest gross margin? What is the average order value by channel? Do Autoship customers spend more than one-time buyers? Which customers haven't ordered in the last 180 days?

CoCo runs a discovery scan (catalog search, existing contexts, warehouse and role, and a background query-history scan), then shows a proposed scope card. Expect something like:

```
─── PAWPRIME_SALES · scope ─────────────────────────  proposed

  INCLUDE — pulled into scope
    Tables
      CORTEX_SENSE_DEMO.WORKSHOP.*          │  4  CUSTOMER, PRODUCT, ORDERS, ORDER_ITEM
    Semantic Views
      CORTEX_SENSE_DEMO.WORKSHOP.SV_PET_STORE │ 1

  EXCLUDE — kept out of every answer
    ...

  build · include <pattern> · exclude <pattern> · deeper · refresh
```

Review the scope before building:

- **If CoCo asks for the domain**, reply `domain = pawprime-sales`.
- **If it pulls in unrelated objects** (for example the game demo schemas), remove them:
  > exclude CORTEX_SENSE_DEMO.GAME_SALES.*

  > exclude CORTEX_SENSE_DEMO.GAME_CATALOG.*
- **If the query-history scan is still running**, type `refresh` to update the card.
- The scan works at the account level, so it may also suggest other sources. Accept or decline each one.

## Step 2: Build the index

When the scope looks right:

**Copy-this-Prompt:**

> build

The build is a background job that turns the scope into the knowledge CoCo uses to answer questions. It runs on your warehouse and can take minutes to hours depending on the scope. This scope is small, so it should be on the shorter end. You don't have to wait in the chat.

You will be prompted to accept the domain description, something like this. Type "Yes" to build.


The scope and notification settings are approved. Before I save and start the build, please confirm the description for **PAWPRIME_SALES**:

> Sales analytics for PawPrime, an online pet-products retailer: customers, products, orders and order line items. Covers net sales, gross margin by product category, average order value by channel, Autoship vs one-time buyer spend, and customer recency/lapsed customers. Revenue comes from ORDER_ITEM.LINE_TOTAL and excludes cancelled orders.

Agents read this to decide whether to use this context for a question, so it's worth getting right.

Type **yes** to accept it, write your own, or type **skip** to save without one.


### Building....

You will see the build is now queued.


Saved. The build is now queued — it can take minutes or hours to complete depending on the scope.

  Build role:      ACCOUNTADMIN  (fixed — recreate to change)
  
  Build warehouse: COMPUTE_WH    (say "use warehouse <NAME>" to change it)
  
  Stored at:       CORTEX_SENSE_DEMO.WORKSHOP
  
  Notification CONTACT: new CONTACT in CORTEX_SENSE_DEMO.WORKSHOP
 
  Notification users:   YOUR_USER_NAME

Email delivery requires each user above to have a configured, verified email.

You don't need to wait. While it runs you can:
  • add more scope — just type here
  • reply here to add facts the build should know
    ("net sales excludes cancelled orders", "gross margin = LINE_TOTAL − cost")
  • turn your 5 example questions into an eval set — say "generate eval"
  • share this as an agent — ask me "set up an agent for PAWPRIME_SALES"

When the build finishes, ask against it by name:
  $cortex-sense query PAWPRIME_SALES about <your question>

If CoCo restarts or you open a new session, type:
  $cortex-sense resume PAWPRIME_SALES




### To check progress later:

**Copy-this-Prompt:**

> What is the build status of the pawprime-sales cortex sense context?

Continue once the build reports it is done.

## Step 3: Ask a baseline question

Ask a question that depends on a business rule the semantic view doesn't enforce.

**Copy-this-Prompt:**

> Using the pawprime-sales context, what were total sales by product category?

Look at the SQL CoCo shows. The `revenue` metric in `SV_PET_STORE` includes **every** order status, including `Cancelled`. Note whether the answer filters out cancelled orders. Write down the total for one category (for example Food) so you can compare it in Lab 3.

## Step 4: Ask more questions in CoCo

Try more questions:

**Copy-this-Prompt:**

> Using the pawprime-sales context, what is the average order value by channel?

**Copy-this-Prompt:**

> Using the pawprime-sales context, do Autoship customers spend more per customer than one-time buyers?

**Copy-this-Prompt:**

> Using the pawprime-sales context, which customers haven't ordered in the last 180 days?

**Copy-this-Prompt:**

> Using the pawprime-sales context, are cat owners buying dog products?

For each answer, check that:

- Revenue comes from `ORDER_ITEM.LINE_TOTAL`
- Cancelled orders are excluded
- Joins match the Lab 1 relationships (`ORDERS.CUSTOMER_ID → CUSTOMER`, `ORDER_ITEM.ORDER_ID → ORDERS`, `ORDER_ITEM.PRODUCT_ID → PRODUCT`)

Note which answers look wrong — for example, any that count cancelled orders as sales. In [Lab 3](lab-3-evaluate-context.md) you'll measure these with an eval and fix them with feedback rules.

## Cleanup

If you're continuing to Lab 3, skip this. The context lives in `CORTEX_SENSE_DEMO.WORKSHOP`, so the Lab 1 teardown removes it along with the tables and semantic view:

```bash
snow sql -c CORTEX_SENSE_DEMO_CONN -f intro-workshop/sql/99_teardown.sql
```
