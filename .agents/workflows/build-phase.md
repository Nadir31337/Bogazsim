---
description: Build the next phase of BoğazSim, run tests, report results, and await approval
---

# /build-phase Workflow

Execute this workflow whenever the user runs `/build-phase` or requests the next phase to be built.

## Step 1: Context & State Discovery
1. Read `AGENTS.md`, `.agents/rules/rubric-and-quality.md`, and `.agents/rules/domain-physics.md`.
2. Review the Task List artifact (or check workspace code) to determine which phases (1 through 8) are already complete.
3. Identify the **single next unfinished phase** $N \in [1..8]$:
   - **Phase 1**: Scaffold: folders, `requirements.txt` (pinned), `core/exceptions.py`, `core/constants.py`
   - **Phase 2**: `core/grid_engine.py` and `core/weather_client.py` (+ tests)
   - **Phase 3**: `core/entities.py`, integrators, `core/simulator.py` (+ tests)
   - **Phase 4**: `core/route_optimizer.py`, A* (+ tests)
   - **Phase 5**: `analytics/data_processor.py` and `analytics/visualizer.py`
   - **Phase 6**: `main.py` FastAPI endpoints (+ endpoint tests)
   - **Phase 7**: Frontend: `templates/index.html`, `static/css/styles.css`, `static/js/dashboard.js`, start server, verify UI at 1280x720 with browser subagent, capture screenshot artifact
   - **Phase 8**: `generate_report_assets.py`, `README.md` (with rubric mapping table), `ARCHITECTURE_AND_QA_GUIDE.md` (class-by-class explanation, 2-minute demo script, $\ge 25$ professor Q&A)

## Step 2: Implementation of Phase $N$
1. Implement strictly the files required for Phase $N$.
2. Tag all rubric features in code comments (e.g. `# RUBRIC: Polymorphism`, `# RUBRIC: Bilinear Interpolation`).
3. Follow code quality standards:
   - Type hints on all functions and methods.
   - Comprehensive docstrings explaining the underlying physics and math in plain English.
   - Functions under ~40 lines.
   - No magic numbers (all constants imported from `core/constants.py`).
   - No placeholders, no `pass`, no `TODO`.
4. If any design decision is made, append it immediately to `AGENTS.md` under the "Assumptions" section.

## Step 3: Test Execution & Self-Correction
1. Run the test suite:
   ```bash
   pytest -q
   ```
2. If any test fails, inspect the failure trace, diagnose the root cause, modify the code, and re-run until 100% of tests pass.
3. Verify that tests run completely offline and do not depend on external network access.

## Step 4: Write Phase Report Artifact
Generate a concise, high-visibility Phase Report artifact in the conversation artifact directory (`<appDataDir>/brain/<conversation-id>/phase-N-report.md`) containing:
1. **Phase Summary**: Exact list of files created or updated and features implemented.
2. **Rubric Tags Applied**: Specific rubric criteria addressed in this phase.
3. **Test Results**: Output summary of `pytest -q` showing passed test cases.
4. **New Assumptions**: Any new assumptions logged in `AGENTS.md`.
5. **Professor Q&A**: Exactly 3 deep technical/domain questions a professor might ask about this phase's code, with rigorous plain-English answers explaining the math and design rationale.

## Step 5: Update Task List Artifact
Update the Task List artifact to mark Phase $N$ as completed and Phase $N+1$ as next up.

## Step 6: STOP and Wait for Approval
- Present the phase report to the user.
- **DO NOT** proceed to the next phase until the user explicitly approves (e.g., says "next" or runs `/build-phase`).

## Step 7: Post-Approval Git Commit (Run when approved)
Once the user confirms approval:
```bash
git add -A
git commit -m "phase N: <short description>"
```
*(e.g., `git commit -m "phase 1: scaffold, constants, and custom exceptions"`)*
