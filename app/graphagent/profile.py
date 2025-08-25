# app/graphagent/profile.py
import os, yaml

def apply_profile(name: str | None):
    if not name:
        return
    here = os.path.dirname(__file__)
    path = os.path.join(here, "profiles", f"{name}.yaml")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if ep := cfg.get("llm_endpoint"):
        os.environ["LLM_ENDPOINT"] = ep
    if model := cfg.get("llm_model"):
        os.environ["LLM_MODEL"] = model
