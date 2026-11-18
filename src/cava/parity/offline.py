"""Stub for the Docker-only 'offline' module. Outside Docker we allow nltk downloads
and skip the PEDANT hash check (models already verified in this venv install).
Seeds langdetect for deterministic IFEval language checks (same as the verifier).
"""
import langdetect

langdetect.DetectorFactory.seed = 0


def verify_pedant_models() -> None:
    """No-op outside Docker — models came from pip install."""
    pass
