# OSF pre-registration draft (skeleton)

**Status: skeleton.** To be filled in after the POC validates the pipeline and
before image generation is scaled to the 12 000-image main study. Filing this
on OSF is part of the editorial commitment of the manuscript.

## 1. Study identification

- **Title:** Auditing Algorithmic Pigmentocracy — a multilingual,
  microdata-calibrated audit of phenotype-occupation bias in open-weight T2I
  models for four Latin-American countries.
- **Authors:** Carlos Alfonso Laverde Rodríguez; Yenny Katherine Parra Acosta;
  Henry Laverde Rojas. Universidad Militar Nueva Granada.

## 2. Hypotheses (confirmatory)

- **H1.** For each country and occupation, Δ(o,c,ℓ,m) < 0 across the four
  main models and four main languages.
- **H2.** Across occupations, β < 0 in `Δ(o) = α + β·w(o) + γ·X(o) + ε`,
  pooled by (country, language, model).
- **H3.** Adding language fixed effects to `APD(c,ℓ,m) = α_m + δ_c + λ_ℓ + ε`
  yields jointly significant λ.
- **H4.** Across model versions with shared architecture, larger parameter
  counts do not produce a monotone reduction in |APD|.
- **H5.** Prompts with Latin-American geographic markers produce higher
  CLIP-zero-shot probability of rural/folkloric backgrounds than equivalent
  prompts with US/EU markers.

## 3. Sampling

- 25 occupations × 4 models × 4 languages × 30 images = 12 000 main images.
- 10-occupation subset × 4 extra models × 2 indigenous languages × 10 images
  = ~3 200 robustness images.

## 4. Analysis plan (locked before main run)

- Pre-registered primary specifications and robustness alternatives, with
  decision rules separating confirmatory from exploratory inferences.

## 5. Exploratory analyses (declared as such)

- Indigenous-language prompts (quechua, guarani).
- Per-occupation MST/CASCo concordance breakdowns.

## 6. Open materials

- All code, prompts, image metadata (not images themselves), derived panels,
  bootstrap replicates and figures will be archived on GitHub + Zenodo with a
  permanent DOI at submission.

(To be expanded in the actual pre-registration form on OSF.)
