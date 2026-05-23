---
name: agent-platform-workflows
description: Use when working on this repository's FastAPI backend, Vue frontend, Agent tools, project documentation, or GitHub delivery workflow.
---

# agent_platform Workflows

Use this skill for changes in the `agent_platform` repository.

## First Checks

- Read `sum/documents/project_and_skills.md` before larger changes.
- Check `git status --short --branch` before editing.
- Keep `.env`, logs, vector stores, database files, and `node_modules` out of commits.
- Treat `backed/` as backend production code and `travel_frontend/` as frontend production code.
- Treat `test/` as mixed experiments until it is reorganized.

## Backend Workflow

- Entry point: `backed/main.py`.
- Routers: `backed/routers/`.
- Database access: `backed/crud/`, `backed/models/`, `backed/schema/`.
- Agent orchestration: `backed/agent/sup_agent.py`.
- Agent tools: `backed/agent/agent_tools/`.
- Prefer environment variables over hardcoded secrets or local-only paths.
- Keep API response shapes compatible with the frontend unless updating both sides together.

## Frontend Workflow

- App entry: `travel_frontend/src/main.ts`.
- Routes: `travel_frontend/src/router/index.ts`.
- HTTP client: `travel_frontend/src/utils/request.ts`.
- Chat UI: `travel_frontend/src/views/chat/index.vue`.
- Prefer small Vue components or composables when chat-page logic grows.
- Verify `npm run build` after frontend behavior changes when dependencies are available.

## Documentation Workflow

- Update `sum/documents/project_and_skills.md` when changing architecture, startup steps, dependencies, skills, deployment, or team conventions.
- Add dated notes to the update log.
- Keep this skill focused on repository workflow, not long architecture explanations.

## Known Cleanup Themes

- Fix mojibake Chinese text carefully and preserve behavior.
- Move all secrets and local config into `.env` / `.env.example`.
- Tighten CORS and Markdown rendering before production.
- Split production tests from learning experiments.
- Add backend and frontend smoke tests before major refactors.
