"""Code-owned recipe registry. Repository uploads never contribute entries."""
from .pocketflow import POCKETFLOW

REGISTRY = {POCKETFLOW.id: POCKETFLOW}
