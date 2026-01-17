from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from .memory import FactLedger
import uvicorn

app = FastAPI(title="TrueBrief Delta Engine API")

# Path to static files
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ledger = FactLedger()

@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/alphas")
async def get_alphas():
    """
    Returns all verified facts found so far.
    """
    facts = ledger.get_all_facts()
    return {"count": len(facts), "alphas": facts}

@app.post("/scan")
async def trigger_scan():
    """
    Triggers a manual scan of the configured feeds.
    """
    from .radar import Radar
    from .sniper import Sniper
    from .engine import Atomizer, NoveltyFilter
    
    radar = Radar()
    sniper = Sniper()
    atomizer = Atomizer()
    engine = NoveltyFilter(memory=ledger) # Use shared ledger to avoid Qdrant lock
    
    targets = radar.scan_feed("https://techcrunch.com/feed/")
    targets = targets[:1] # Limit to 1 for high-quality extraction without 429 limits

    
    new_alphas = 0
    from .verifier import TruthAgent
    verifier = TruthAgent()

    for t in targets:
        content = await sniper._shoot_async(t['url'])
        if not content: continue
        
        # Cluster Extraction: Process the whole text at once for best Alphas
        potential_alphas = verifier.extract_alphas(content)
        
        for alpha in potential_alphas:
            # Check novelty against the ledger
            is_novel, score, match = engine.memory.is_novel(alpha)
            if is_novel:
                engine.commit(alpha, t['url'])
                new_alphas += 1

                
    return {"status": "success", "new_alphas_discovered": new_alphas}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
