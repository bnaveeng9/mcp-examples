---
name: mcp-fastapi-scaffolding
description: "Scaffold a Python MCP application using FastMCP with an optional FastAPI wrapper. Use when creating a new MCP server, adding tools, prompts, resources, HTTP endpoints, local run modes, or a deployable app based on this project's patterns."
---

# Scaffold a Python FastMCP Application

Create or extend a Python application that exposes MCP tools, prompts, and resources using FastMCP. Add a FastAPI wrapper when the app needs ordinary HTTP endpoints alongside MCP. Use the user's target project and requirements as the source of truth; treat this repository as a reference, not as code to copy wholesale.

## When to Use

- Create a new Python MCP server or starter application.
- Add MCP tools, prompts, or resources to an existing Python app.
- Expose MCP and ordinary HTTP endpoints through one FastAPI application.
- Add a local launch command or a standalone Streamable HTTP mode.
- Adapt the examples in this repository to another app or integration.

## Workflow

1. **Inspect before scaffolding**
   - Read the target repository's README, dependency and build configuration, source layout, and existing tests.
   - Identify its Python version, package manager, naming conventions, entry points, deployment needs, and existing MCP or HTTP wiring.
   - Ask for clarification if essential choices such as transport, hosting, or required integrations are unclear. Otherwise, use the simplest option consistent with the project.

2. **Choose a package structure**
   - Follow the target project's existing structure when possible.
   - For a new `src/`-layout project, use a small package with dedicated modules for server wiring and capability registration. For example:
     ```text
     src/<package_name>/
       __init__.py
       __main__.py
       server.py
       tools/
       prompts/
       resources/
     ```
   - Keep tools, prompts, resources, and ordinary HTTP endpoints in separate modules as the project grows. Avoid creating empty or unnecessary modules.

3. **Wire one server entry point**
   - Create a single FastMCP instance in the server module.
   - Register capabilities through focused `register(mcp)` functions that accept the FastMCP instance. Keep registration logic close to each capability's implementation.
   - If the app needs HTTP routes, create a FastAPI app, register routes through focused functions such as `register(app)`, and mount the MCP HTTP app at a documented path.
   - Keep app creation and startup behavior in one authoritative server module. Have `__main__.py` and any package script delegate to its `main()` function rather than duplicate startup logic.
   - Use a stateless HTTP MCP configuration only when it matches the deployment and session requirements.

4. **Implement capabilities**
   - Define small, typed tools with clear docstrings, meaningful input validation, and explicit error behavior.
   - Use async functions for asynchronous I/O. Return structured data when that is more useful than formatted output.
   - Add prompts for reusable, parameterized instructions and resources for data the MCP client should read.
   - Keep ordinary HTTP health and application routes separate from MCP protocol routes.
   - Do not expose demo values, placeholder credentials, or personal data as production behavior.

5. **Configure dependencies and commands**
   - Add only dependencies required by the target application and use its existing package manager and Python version policy.
   - Provide a module entry point and, when appropriate, a package command that invoke the same server startup function.
   - Make host, port, transport, and mode behavior explicit. If offering both FastAPI and standalone MCP modes, document when to use each and avoid conflicting listeners.
   - Keep secrets out of source control. Read integration credentials from the target project's established secret or environment-variable mechanism, validate required settings, and report actionable errors.

6. **Document how to run and extend it**
   - Explain setup, launch commands, transport, MCP mount path, ordinary HTTP routes, and any required integration settings.
   - Document example tools, prompts, and resources only if they exist in the implementation.
   - Include a short guide for adding a capability: implement it, register it, and verify it through the relevant interface.
   - Do not claim endpoints or launch modes that have not been implemented and checked.

7. **Validate the result**
   - Run the smallest relevant formatter, linter, type check, or test command available in the target project.
   - Check that the package imports and that documented launch commands use the actual entry point.
   - Verify HTTP routes with suitable requests and verify MCP capabilities using an MCP-aware client or existing tests; a browser GET alone does not validate MCP protocol behavior.
   - If a mode starts a long-running process, confirm it is responsive, then stop it cleanly.
   - Report what was verified and clearly identify anything that could not be tested.

## Reference Pattern

This repository uses a FastMCP server with registration modules, a FastAPI app that mounts the MCP HTTP app, and a `main()` function for startup. Its HTTP wrapper exposes health and demonstration routes; its MCP registrations demonstrate tools, prompts, and resources. Use those as patterns, not as mandatory endpoints or features.

Before borrowing an example integration, inspect its authentication and runtime requirements. For example, Gmail access requires OAuth configuration and user authorization; do not copy credentials, tokens, or real mailbox data into a new app.

## Completion Checklist

- [ ] The target application's package and entry points follow its conventions.
- [ ] MCP tools, prompts, and resources are registered on the intended server instance.
- [ ] Any FastAPI routes and MCP mount path are documented accurately.
- [ ] Dependencies and configuration are appropriate for the target app.
- [ ] Secrets and personal data are not embedded in source or example outputs.
- [ ] Relevant tests or runtime checks pass, and unverified behavior is called out.