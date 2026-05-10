# Coding Patterns & Conventions
> Read this only when building code and unsure about project conventions.

## Error Handling
- Use try/except with specific exceptions
- Log errors with context (module name, operation, input that caused it)
- Never silently swallow exceptions

## Config Access
- All config in `config/settings.py`
- LLM models defined in `LLM_CONFIG` dict
- Env vars loaded via `python-dotenv` from `.env`

## Database
- All DB operations go through `ledger/` module
- Supabase client initialized in `database.py`
- RPCs defined in Supabase dashboard, called from Python
- Migrations in `scripts/migrations/`

## LLM Calls
- All LLM calls go through `llm/` module
- Model config in `config/settings.py` → `LLM_CONFIG`
- Never hardcode model names — always reference config

## Testing
- Unit tests in `tests/`
- Integration test scripts in `scripts/`
- Use pytest
- Always run existing tests before writing new code

## Naming
- Python: snake_case for files, functions, variables
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE
- DB tables: snake_case (Supabase convention)

## Git Commits
```
p{N}-s{X}: {what was done}          ← build step
plan-p{N}: {what was planned}       ← planning
review-p{N}: {what was fixed}       ← review
handoff: end of session p{N}-s{X}   ← session end
```
