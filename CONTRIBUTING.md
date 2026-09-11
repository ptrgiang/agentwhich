# Contributing

Thanks for helping make AI coding context less mysterious.

## Local setup

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
```

## Resolver changes

A resolver change should include:

1. an authoritative vendor-documentation link when available;
2. a small filesystem fixture or focused unit test;
3. an explanation of whether the behavior is startup, import, target-dependent, lazy, or unknown.

Never execute discovered instructions or add required network calls to the core package.
