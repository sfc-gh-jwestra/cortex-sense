# Cortex Agents: `agent_router`

## Warning: This is a preview, undocumented feature subject to change! It is not supported by Snowflake at this time.

## Capability summary

`agent_router` is a native Cortex Agent tool used to route a user’s request to the most appropriate registered sub-agent. It enables a single front-door agent—such as a Snowflake CoWork or Snowflake Intelligence primary agent—to coordinate multiple domain-specific agents without requiring the user to select one manually.

The feature is intended for multi-agent routing scenarios and may be subject to preview availability and behavior changes depending on the account release and product configuration.

## How it works

A typical request follows this pattern:

1. The user submits a natural-language request to the primary agent.
2. The primary agent evaluates the request against the available sub-agents.
3. `agent_router` selects and invokes the most appropriate sub-agent.
4. The selected sub-agent uses its own configured tools and instructions to answer.
5. The result is returned to the user through the primary-agent experience.

This provides a single conversational entry point while allowing individual agents to remain specialized—for example, sales, finance, support, or operations agents.

## Example configuration

A minimal router tool specification is:

```yaml
tools:
  - tool_spec:
      type: agent_router
      name: router
```

In a multi-agent deployment, the router is associated with a set of registered sub-agents. A representative configuration is:

```yaml
tools:
  - tool_spec:
      type: agent_router
      name: router

tool_resources:
  router:
    subagents:
      - name: MY_DB.MY_SCHEMA.SALES_AGENT
      - name: MY_DB.MY_SCHEMA.FINANCE_AGENT
      - name: MY_DB.MY_SCHEMA.SUPPORT_AGENT
```

The exact router resource schema and administrative experience can vary by release. The important design principle is that the primary agent has a router tool and an explicitly curated set of sub-agents available for routing.

Cortex Agent specifications represent tools through `tool_spec` entries, with the tool name used to associate the specification with its corresponding configuration in `tool_resources`. See the [Cortex Agents REST API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api) for the general agent and tool specification model.

## `agent_router` compared with `agent_toolset`

These tools solve different architectural problems:

| Capability | `agent_router` | `agent_toolset` |
|---|---|---|
| Primary purpose | Selects and routes a request to a sub-agent | Reuses another agent’s tools in the calling agent |
| Control flow | The selected sub-agent handles the request | The calling agent remains in control |
| User experience | One front door across multiple specialists | Usually invisible tool reuse within one agent |
| Best for | Domain-based delegation and agent selection | Sharing capabilities while keeping one orchestration loop |
| Cost and latency | May involve a separate sub-agent execution | Typically avoids a second full agent run |

An `agent_toolset` reference is resolved at run time and its tools are expanded into the calling agent’s effective tool set. Snowflake documents this pattern in [Agent toolsets](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-toolsets).

## When to use `agent_router`

Use `agent_router` when:

* Users should ask questions naturally without choosing a specialist.
* Your organization has multiple agents with clearly separated domains.
* Each specialist needs its own tools, instructions, permissions, or governance boundary.
* You want a centralized primary agent for Snowflake CoWork or Snowflake Intelligence.

A single agent with Cortex Analyst, Cortex Search, custom tools, or skills may be preferable when the work is tightly coupled or does not require domain separation. Deterministic routing—such as application logic, keyword rules, or explicit tool allowlists—may also be preferable when the classification decision is simple and predictable.

## Design recommendations

### Define clear agent boundaries

Each sub-agent should have a concise description of:

* The business domain it owns.
* The types of questions it can answer.
* The tools or data sources it is allowed to use.
* Requests it should decline or hand back to the router.

Clear boundaries improve routing quality and reduce overlap between specialists.

### Keep the primary agent focused

The primary agent should primarily coordinate routing and provide a consistent user experience. Avoid adding unrelated tools or instructions that could cause it to answer directly when a specialist should be invoked.

### Preserve context

A routed sub-agent must receive enough context to understand the user’s request, relevant conversation history, and any constraints established by the primary agent. Context loss can lead to incorrect routing or incomplete answers.

### Govern access explicitly

The user’s role must be able to access the primary agent and the agents it may invoke. Apply least-privilege access to each agent and its underlying tools, semantic views, search services, functions, and procedures.

### Test the published configuration

Validate the live or published agent specification—not only the draft configuration. Confirm that:

* The primary agent contains the `agent_router` tool.
* The intended sub-agents are present in the router configuration.
* The executing role can access the primary agent and routed agents.
* Representative questions reach the expected specialist.
* The primary agent still behaves correctly after administrative changes.

## Common & Known issues

### The sub-agents do not appear as tools in Snowsight

Known issue. When you view the router agent's tools, sub-agents are not displayed.

### The primary agent answers directly instead of routing

Check that the published primary-agent specification still contains the `agent_router` tool and that the router’s sub-agent configuration is populated. Also verify that the primary agent’s instructions do not encourage it to answer questions that belong to a specialist.

### A specialist is never selected

Review the specialist’s name and description, reduce overlap with other sub-agents, and test with representative questions. Verify that the intended agent is included in the router’s registered sub-agent list and is accessible to the executing role.

### Configuration changes affect routing

After changing tools, instructions, or administrative settings, re-check the resulting published specification and run routing tests. Treat the router definition as a required part of the primary-agent configuration rather than as an optional convenience.

## Summary

`agent_router` provides a native front door for multi-agent Cortex Agent deployments. It is best suited for organizations that want one conversational experience backed by multiple specialized agents. For capability reuse inside one orchestration loop, use `agent_toolset`; for a small number of tightly coupled capabilities, a single agent may be simpler and more reliable.

## References

* [Github agent_router CoCo skill](https://github.com/sfc-gh-obenning/cortex-skill-add-subagents)
* [Cortex Agents REST API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api)
* [Create and manage agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage)
* [Agent toolsets](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-toolsets)
* [CREATE AGENT](https://docs.snowflake.com/en/sql-reference/sql/create-agent)
