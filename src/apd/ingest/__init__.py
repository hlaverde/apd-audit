"""Public-microdata ingestion (DANE, INEGI, IBGE, INEI, LAPOP, PERLA core).

Each loader returns a pandas DataFrame in a normalised schema documented in
the function docstring. Raw downloads always land in ``data/raw`` and are
never modified in place.
"""
