# Cost log

The central editorial claim of this project is that it can be reproduced at
zero monetary cost. Every action that consumes compute or storage — even when
free — must be recorded here. The cumulative column must always read
**$0.00**.

| Date (UTC) | Action | Provider | Quantity | Marginal cost | Cumulative |
|---|---|---|---|---|---|
| 2026-05-14 | Project bootstrap (skeleton, git init) | local | — | $0.00 | **$0.00** |
| 2026-05-14 | `pip install --user uv` | local (PyPI free) | 1 package | $0.00 | **$0.00** |
| 2026-05-14 | `uv python install 3.11` | Astral/Python.org free CDN | 24.5 MiB | $0.00 | **$0.00** |
| 2026-05-14 | `winget install ezwinports.make` | Microsoft Store / GitHub free | 383 KB | $0.00 | **$0.00** |

Append further entries below as the pipeline runs. Every row must justify why
it cost $0.00 (which free tier / which open dataset / which local resource).

## Conventions

- **Action** is one short verb phrase: `download`, `generate`, `classify`, …
- **Provider** is the free tier used: `HF free`, `Colab T4`, `Kaggle GPU`,
  `local`, etc.
- **Quantity** captures units that matter for free-tier accounting (number of
  images, number of API calls, hours of GPU).
- If a row would have a positive marginal cost, **the action is not taken**
  and the alternative is documented in `DECISIONS.md`.
| 2026-05-15 04:04 UTC | generate POC | cache free | 30 imgs / 286s | $0.00 | **$0.00** |
| 2026-05-15 21:42 UTC-5 | shift hl#1 | Pollinations free | 50 imgs / 73 min (88s/img) | $0.00 | **$0.00** |
| 2026-05-16 12:08 UTC | probe TAREA 1 | Pollinations free | 80 imgs / 1982s (N=1: 20/20 OK ~90s/img; N=3,5,10: 1/20 OK each, 19x 402) | $0.00 | **$0.00** |
