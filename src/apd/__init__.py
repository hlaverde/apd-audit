"""Auditing Algorithmic Pigmentocracy — empirical pipeline.

Sub-packages:
    ingest        Public microdata downloaders (DANE, INEGI, IBGE, INEI, LAPOP).
    ground_truth  Construction of f_emp(t|o,c) and status weights w(o,c).
    prompts       Prompt grid across occupations × languages × models.
    generate      Image generation backends (HF, Colab, Kaggle, local).
    classify      Face detection, skin-tone (CASCo/ITA/MST), FairFace, CLIP.
    panel         Per-(model, occupation, country, language) panel builder.
    apd           APD indicator: distances, signed Δ, status-weighted aggregate.
    estimate      Econometric specifications for H1-H5.
    viz           Publication-quality figures.
"""

__version__ = "0.1.0"
