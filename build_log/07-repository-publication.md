# Repository Publication

## 2026-08-17 — Commit and push

After the final acceptance suite passed, the exact deliverable set was staged and checked with `git diff --cached --check`. The ignored `.env`, Python caches, virtual environment, supplied assignment directory, and `starter_agent.py` were absent from the staged tree.

The audited implementation was committed on `main` as `9229335` (`Build grounded observable AI tutor`). A private GitHub repository was then created at <https://github.com/GalDaich/tavily-ai-tutor>, configured as `origin`, and pushed with `main` as the default branch.

Post-push verification confirmed that local `HEAD` and `origin/main` resolved to the same commit. The GitHub tree contained only the intended application, tests, documentation, build-log entries, dependency files, and safe environment-variable template. It did not contain `.env` or the supplied assignment materials.

The repository remains private by default because it is a take-home submission. Before sending the link, either grant the Tavily reviewers access or intentionally change the repository visibility.
