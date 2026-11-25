"""Portable defaults; secrets are supplied by the operating system credential store."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.getenv("SAFEON_BASE_URL", 'https://api.deepseek.com')
API_KEY = os.getenv("SAFEON_API_KEY", "")
MODEL = os.getenv("SAFEON_MODEL", 'deepseek-v4-pro')
NEO4J_URI = os.getenv("SAFEON_NEO4J_URI", "bolt://127.0.0.1:7687")
NEO4J_USER = os.getenv("SAFEON_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("SAFEON_NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("SAFEON_NEO4J_DATABASE", "safeon")
