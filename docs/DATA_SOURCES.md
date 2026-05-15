# Data sources

Every URL listed here was verified accessible without institutional
credentials at the date noted. License and retrieval date are mandatory.

## Public microdata for ground truth

### Colombia

| File | Origin | URL | Retrieved | License | Used in |
|---|---|---|---|---|---|
| LAPOP AmericasBarometer Colombia 2023 | Vanderbilt LAPOP Lab | https://www.lapopsurveys.org/data-access | TBD (POC run) | LAPOP open-data terms (free, attribution required) | POC ground truth |
| GEIH 2023 (DANE) — pending sample evaluation | DANE | https://microdatos.dane.gov.co | TBD | DANE open-microdata licence | Excluded if registration required |

### Mexico

| File | Origin | URL | Retrieved | License | Used in |
|---|---|---|---|---|---|
| ENADIS 2022 (INEGI) | INEGI | https://www.inegi.org.mx/programas/enadis/2022/ | (not yet) | INEGI open-data terms | Production |
| LAPOP Mexico 2023 | Vanderbilt LAPOP Lab | https://www.lapopsurveys.org/data-access | (not yet) | LAPOP open-data terms | Production |

### Brazil

| File | Origin | URL | Retrieved | License | Used in |
|---|---|---|---|---|---|
| PNADC 2023 (IBGE) | IBGE | https://www.ibge.gov.br/estatisticas/sociais/trabalho/9171 | (not yet) | IBGE open-data terms | Production |
| LAPOP Brazil 2023 | Vanderbilt LAPOP Lab | https://www.lapopsurveys.org/data-access | (not yet) | LAPOP open-data terms | Production |

### Peru

| File | Origin | URL | Retrieved | License | Used in |
|---|---|---|---|---|---|
| ENAHO 2023 (INEI) | INEI | https://www.inei.gob.pe/microdatos | (not yet) | INEI open-data terms | Production |
| LAPOP Peru 2023 | Vanderbilt LAPOP Lab | https://www.lapopsurveys.org/data-access | (not yet) | LAPOP open-data terms | Production |

### Auxiliary (all four countries)

| File | Origin | URL | Retrieved | License | Used in |
|---|---|---|---|---|---|
| PERLA Project core surveys 2010 | Princeton / UCSB | https://perla.princeton.edu | (not yet) | PERLA project terms | Imputation crosswalks |

## Generative models (open weights, free)

All accessed through the Hugging Face Hub (free Inference API or local
`diffusers` weights). Hub URLs:

| Model | URL | License |
|---|---|---|
| Stable Diffusion 1.5 | https://huggingface.co/runwayml/stable-diffusion-v1-5 | CreativeML Open RAIL-M |
| Stable Diffusion 2.1 | https://huggingface.co/stabilityai/stable-diffusion-2-1 | CreativeML Open RAIL++-M |
| Stable Diffusion XL 1.0 | https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0 | CreativeML Open RAIL++-M |
| Stable Diffusion 3.5 Medium | https://huggingface.co/stabilityai/stable-diffusion-3.5-medium | Stability AI Community |
| FLUX.1 Schnell | https://huggingface.co/black-forest-labs/FLUX.1-schnell | Apache 2.0 |
| Playground v2.5 | https://huggingface.co/playgroundai/playground-v2.5-1024px-aesthetic | Playground v2.5 Community |
| Kandinsky 3 | https://huggingface.co/kandinsky-community/kandinsky-3 | Apache 2.0 |
| AltDiffusion (multilingüe) | https://huggingface.co/BAAI/AltDiffusion-m18 | CreativeML Open RAIL-M |

## Classifiers and computer-vision toolkits (open source)

| Tool | URL | License |
|---|---|---|
| MediaPipe Face Detection | https://github.com/google-ai-edge/mediapipe | Apache 2.0 |
| OpenCV (used for CIE-Lab → ITA) | https://opencv.org | Apache 2.0 |
| CASCo (Rejón Piña 2023) | https://github.com/(to be vendored) | TBD — verify before use |
| Monk Skin Tone scale | https://skintone.google | CC BY (reference) |
| FairFace | https://github.com/joojs/fairface | MIT |
| CLIP (for H5 context) | https://huggingface.co/openai/clip-vit-base-patch32 | MIT |

## Occupational crosswalks (public)

| Crosswalk | URL | License |
|---|---|---|
| ISCO-08 ↔ CNO-2015 (Colombia) | DANE classifications portal | DANE open-data |
| ISCO-08 ↔ SINCO-2011 (Mexico) | INEGI classifications portal | INEGI open-data |
| ISCO-08 ↔ CBO (Brazil) | IBGE concorda portal | IBGE open-data |
| ISCO-08 ↔ COP (Peru) | INEI classifications portal | INEI open-data |
