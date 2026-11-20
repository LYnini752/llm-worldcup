# Notice

## LLM World Cup

Copyright (c) 2026 LLM World Cup contributors.

This project is licensed under the MIT License; see [LICENSE](LICENSE) for the full text.

## Synthetic demo data

Files under `examples/` marked `"synthetic": true` are hand-written fixtures for
development and UI preview. They do **not** represent output from any real model,
vendor, or benchmark, and must not be cited as model performance evidence.

## Third-party dependencies

Third-party packages (including the runtime UI framework and test tooling listed in
`requirements.txt` / `requirements-dev.txt`) retain their own copyrights and
licenses. Their license terms are independent of this project's MIT license.

Known direct dependencies and their declared license metadata (verify again at
packaging time with `pip show <package>`):

- `gradio` — Apache-2.0
- `pytest` — MIT
- `ruff` — MIT

All transitive dependencies retain their respective licenses.

### Transitive license audit (2026-11-20, project `.venv`)

An audit of every installed distribution in the project virtualenv (via
`importlib.metadata`) found only permissive, OSI-approved license families:

- Apache-2.0 (including dual-licensed Apache-2.0 / MIT / MPL-2.0 packages)
- MIT / MIT-CMU
- BSD-2-Clause / BSD-3-Clause / BSD
- MPL-2.0 (dual-licensed)
- PSF-2.0, ISC, and 0BSD / CC0-1.0 / Zlib permissive terms bundled in numpy

No GPL / AGPL / LGPL or proprietary-license distribution was observed. This
audit covers installed distributions in the development virtualenv; when
packaging or redistributing, re-run `pip show <package-name>` (or
`pip-licenses`) against the built artifact and retain each upstream license and
NOTICE text according to its terms.

To inspect installed packages and their license metadata in your virtualenv:

```bash
.venv/bin/pip show <package-name>
```

If you redistribute this project, please verify and retain the license notices of
every bundled third-party dependency according to its terms.
