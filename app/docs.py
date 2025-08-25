DOCS = [
    "Xeriscape (drought-tolerant) designs rely on native/adapted plants, mulch, and efficient drip irrigation; water use can drop 30–60% vs. traditional turf.",
    "Traditional lawn-centric front yards emphasize uniform turf; aesthetics are formal/green but require frequent mowing, fertilization, and irrigation.",
    "Colorado landscapes benefit from mulch (2–4 inches) to suppress weeds, moderate soil temperature, and reduce evaporation.",
    "Drought-tolerant gardens often need more maintenance in year 1 (establishment) and less thereafter; hand weeding and seasonal pruning are typical.",
    "Inputs comparison: turf lawns usually require regular irrigation (1–1.5 inches/week in summer), N-rich fertilizer 2–4×/season, and pest control; xeriscape reduces irrigation frequency and fertilizer needs.",
]

def search_docs(q: str, k: int = 3) -> list[str]:
    ql = q.lower()
    scored = sorted(DOCS, key=lambda d: -sum(w in d.lower() for w in ql.split()))
    return scored[:k]

