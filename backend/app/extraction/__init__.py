"""Evidence extraction from uploaded bid PDFs.

Pipeline: `pdf` reads text page by page -> `rules` (deterministic patterns)
or `ai` (Claude, via the AIProvider interface) turns that text into the
same per-field evidence the seeded demo documents carry -> the existing rule
engine (`app.evaluation.mock_evaluator`) decides every verdict.
"""
