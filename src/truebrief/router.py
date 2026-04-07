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
async def get_alphas(topic: str = None):
    """
    Returns all verified facts found so far.
    """
    facts = ledger.get_all_facts(topic_filter=topic)
    return {"count": len(facts), "alphas": facts}

from pydantic import BaseModel

class ScanRequest(BaseModel):
    feed_url: str = "https://techcrunch.com/feed/"

@app.post("/scan")
async def trigger_scan(request: ScanRequest):
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
    
    # Check if input is a Topic or a URL
    targets = []
    
    if request.feed_url.startswith("http"):
        # Direct Mode (URL)
        print(f"📡 Radar locked on direct target: {request.feed_url}")
        targets = radar.scan_feed(request.feed_url)
    else:
        # Librarian Mode (Topic)
        print(f"🧙‍♂️ Librarian Activate! Researching topic: {request.feed_url}")
        from .librarian import Librarian
        lib = Librarian()
        lib_res = lib.search_sources(request.feed_url)
        
        if not lib_res.get("official_name"):
            return {
                "status": "failed",
                "reason": "Topic was rejected by Intent Analyzer as gibberish."
            }
            
        sources_dict = lib_res.get("sources", {"rss": [], "static": []})
        official_name = lib_res["official_name"]
        
        # 1. Harvest RSS Feeds (Commodity Context)
        for rss in sources_dict['rss']:
            print(f"   📡 Scanning found feed: {rss}")
            t = radar.scan_feed(rss)
            targets.extend(t)
            
        # 2. Harvest Static Targets (High Value Alpha)
        for static_url in sources_dict['static']:
            print(f"   🎯 Locking onto Static Target: {static_url}")
            # Mock a target object so Sniper accepts it
            targets.append({
                'url': static_url,
                'title': f"Static Target: {static_url}",
                'published': "Today"
            })
    
    new_alphas = 0
    from .verifier import TruthAgent
    verifier = TruthAgent()

    # 1. Collect Content (The Hunter)
    contents = []
    valid_targets = []
    
    # Process up to 5 articles in a batch
    batch_targets = targets[:5]
    
    print(f"🎯 Sniper targeting {len(batch_targets)} articles for batch analysis...")
    
    for t in batch_targets:
        sniper_result = await sniper._shoot_async(t['url'])
        if sniper_result and sniper_result.get("text"):
            contents.append(sniper_result["text"])
            if sniper_result.get("published_date"):
                t['published'] = sniper_result["published_date"]
            valid_targets.append(t)
    
    # Track precise failure metrics
    sources_found = len(valid_targets)
    scraped_successfully = len(contents)
    total_alphas_extracted = 0
    
    # 2. Batch Verification (The Brain)
    if contents:
        print(f"🧠 Batch Analyzing {len(contents)} articles for '{request.feed_url}'...")
        # Use the finalized official name
        topic_name = official_name if not request.feed_url.startswith("http") else request.feed_url
        batch_results = verifier.extract_alphas_batch(contents, topic_name=topic_name)
        
        total_alphas_extracted = len(batch_results)
        
        for item in batch_results:
            alpha_text = item.get('text')
            src_idx = item.get('source_index')
            
            if alpha_text and src_idx is not None and 0 <= src_idx < len(valid_targets):
                source_url = valid_targets[src_idx]['url']
                published_date = valid_targets[src_idx].get('published', '')
                
                is_saved, final_fact = engine.process_extracted_alpha(alpha_text, source_url, published_date, topic_name=topic_name)
                if is_saved:
                    new_alphas += 1

    rejected_by_verifier = total_alphas_extracted - new_alphas

    return {
        "status": "success", 
        "new_alphas_discovered": new_alphas,
        "metrics": {
            "sources_found": sources_found,
            "scraped_successfully": scraped_successfully,
            "extracted_by_llm": total_alphas_extracted,
            "rejected_by_engine": rejected_by_verifier
        }
    }

# --- Topic Manager API ---
from .topics import TopicManager
topic_manager = TopicManager()

@app.get("/topics")
async def get_topics():
    return {"topics": topic_manager.get_all_topics()}

class TopicRequest(BaseModel):
    name: str

from fastapi import BackgroundTasks
from fastapi import HTTPException

@app.post("/topics")
async def add_topic(request: TopicRequest, background_tasks: BackgroundTasks):
    """
    Adds a new topic. Uses Librarian to find sources automatically.
    Triggers an immediate background scan.
    """
    from .librarian import Librarian
    lib = Librarian()
    
    # Auto-Discover Sources
    print(f"🧙‍♂️ Librarian Scouting sources for new topic: {request.name}")
    lib_res = lib.search_sources(request.name)
    official_name = lib_res.get("official_name")
    
    if not official_name:
        raise HTTPException(status_code=400, detail="Topic rejected as invalid or gibberish by TrueBrief Intent Analyzer.")
        
    sources_dict = lib_res.get("sources", {"rss": [], "static": []})
    
    # Save to Persistence (Using Official Name)
    new_topic = topic_manager.add_topic(official_name, sources_dict)
    
    # Trigger Immediate Scan
    from .manager import SurveillanceManager
    # Pass the global ledger to avoid locking the DB
    mgr = SurveillanceManager(ledger=ledger)
    print(f"⚡ Triggering Immediate Scan for {official_name}...")
    background_tasks.add_task(mgr.scan_topic, new_topic)
    
    return {"status": "success", "topic": new_topic}

@app.delete("/topics/{topic_name}")
async def delete_topic(topic_name: str):
    """
    Deletes a topic from the manager and erases all associated intelligence from Qdrant.
    """
    topic_manager.delete_topic(topic_name)
    ledger.delete_facts_by_topic(topic_name)
    return {"status": "deleted", "topic": topic_name}



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
