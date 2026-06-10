# Presets

`testradar` ships with an optional Django preset.

## Django preset

Enable it with:

```toml
[tool.testradar]
preset = "django"
```

The preset adds:

- `settings*.py` and `manage.py` as full-suite triggers.
- `requirements/` changes as full-suite triggers.
- `migrations/*.py` as app-scoped selectors.
- Django coupling detectors for `apps.get_model(...)`, `@receiver(..., sender="app.Model")`, and `.connect(sender="app.Model")`.

## Custom detectors

Extra detectors can be registered in config with import paths:

```toml
[tool.testradar]
detectors = ["myproject.testradar:CustomDetector"]
```

Each detector returns extra import requests that get resolved into graph edges.
