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
| 2026-05-24 02:34 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-24 08:22 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-24 13:07 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-24 19:07 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-25 02:40 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-25 09:55 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-25 14:41 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-25 19:21 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-26 02:32 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-26 09:39 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-26 14:50 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-26 20:01 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-27 02:41 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-27 09:35 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-27 15:01 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-27 20:06 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-28 02:28 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-28 09:52 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-28 15:35 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-28 20:11 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-29 02:33 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-29 09:41 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-29 14:47 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-29 20:13 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-30 02:16 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-30 08:19 UTC | shift Layer-2 worker | Pollinations free | 2 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-30 13:11 UTC | shift Layer-2 worker | Pollinations free | 4 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-30 19:05 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-31 02:44 UTC | shift Layer-2 worker | Pollinations free | 4 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-31 08:39 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-31 13:23 UTC | shift Layer-2 worker | Pollinations free | 4 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-05-31 19:08 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-01 02:52 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-01 11:15 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-01 17:24 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-01 21:25 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-02 02:50 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-02 10:10 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-02 16:08 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-02 20:40 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-03 02:58 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-03 16:22 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-06 08:28 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-06 13:14 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-06 19:10 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-07 08:49 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-08 02:49 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-09 14:32 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-10 14:59 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-11 10:11 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-12 10:01 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-12 14:41 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-12 19:58 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-13 02:38 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-13 08:50 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-14 02:52 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-14 13:44 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-15 11:50 UTC | shift Layer-2 worker | Pollinations free | 1 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 02:59 UTC | shift Layer-2 worker | Pollinations free | 24 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:04 UTC | shift Layer-2 worker | Pollinations free | 12 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:09 UTC | shift Layer-2 worker | Pollinations free | 22 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:14 UTC | shift Layer-2 worker | Pollinations free | 18 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:19 UTC | shift Layer-2 worker | Pollinations free | 19 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:24 UTC | shift Layer-2 worker | Pollinations free | 20 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:29 UTC | shift Layer-2 worker | Pollinations free | 20 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:34 UTC | shift Layer-2 worker | Pollinations free | 17 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:39 UTC | shift Layer-2 worker | Pollinations free | 23 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:44 UTC | shift Layer-2 worker | Pollinations free | 19 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:49 UTC | shift Layer-2 worker | Pollinations free | 18 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:54 UTC | shift Layer-2 worker | Pollinations free | 25 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 03:59 UTC | shift Layer-2 worker | Pollinations free | 23 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:04 UTC | shift Layer-2 worker | Pollinations free | 12 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:09 UTC | shift Layer-2 worker | Pollinations free | 24 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:14 UTC | shift Layer-2 worker | Pollinations free | 21 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:19 UTC | shift Layer-2 worker | Pollinations free | 18 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:24 UTC | shift Layer-2 worker | Pollinations free | 25 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:29 UTC | shift Layer-2 worker | Pollinations free | 17 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 04:31 UTC | shift Layer-2 worker | Pollinations free | 12 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 10:58 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 16:28 UTC | shift Layer-2 worker | Pollinations free | 3 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-16 20:43 UTC | shift Layer-2 worker | Pollinations free | 4 imgs / shard checkpoint | $0.00 | **$0.00** |
| 2026-06-17 02:53 UTC | shift Layer-2 worker | Pollinations free | 4 imgs / shard checkpoint | $0.00 | **$0.00** |
