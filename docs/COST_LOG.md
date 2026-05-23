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
| 2026-05-16 12:35 UTC | fix hl#1 mislabel | local | drop 20 rows (D-030) | $0.00 | **$0.00** |
| 2026-05-16 18:10 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-16 18:44 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-16 18:50 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-16 18:55 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-16 19:00 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-16 19:05 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-17 02:18 UTC | shift Layer-2 worker | Pollinations free | 5 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-17 08:14 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-17 13:03 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-17 19:00 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-18 02:37 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-18 09:46 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-18 14:59 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-18 19:30 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 02:35 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 09:33 UTC | shift Layer-2 worker | Pollinations free | 4 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 09:38 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 09:43 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 09:43 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 14:43 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-19 19:47 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-20 02:36 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-20 08:57 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-20 14:43 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-20 16:51 UTC | shift Layer-3 Kaggle | Kaggle T4 free | 20 imgs / 1.7 min | $0.00 | **$0.00** |
| 2026-05-20 20:07 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-21 02:37 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-21 09:01 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-21 14:47 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-21 19:46 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-22 02:37 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-22 08:54 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-22 14:23 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-22 19:26 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-23 02:15 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-23 08:11 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-23 19:01 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
