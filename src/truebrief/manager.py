import asyncio
import time
from .topics import TopicManager
from .librarian import Librarian
from .radar import Radar
from .sniper import Sniper
from .engine import Atomizer, NoveltyFilter
from .memory import FactLedger
from .verifier import TruthAgent

class SurveillanceManager:
    """
    The Autonomous Manager (Mission 2.3).
    Wakes up, reads the Topic List, and executes the Intelligence Cycle for each.
    """
    def __init__(self, ledger=None):
        self.topics = TopicManager()
        self.librarian = Librarian()
        self.radar = Radar()
        self.sniper = Sniper()
        
        if ledger:
            self.ledger = ledger
        else:
            self.ledger = FactLedger()
            
        self.engine = NoveltyFilter(memory=self.ledger)
        self.verifier = TruthAgent()

    async def run_cycle(self):
        """
        Runs one full surveillance cycle across all active topics.
        """
        all_topics = self.topics.get_all_topics()
        print(f"🕵️‍♂️ Starting Surveillance Cycle for {len(all_topics)} targets...")
        
        for topic in all_topics:
            await self.scan_topic(topic)

    async def scan_topic(self, topic):
        """
        Scans a single topic for new Alphas.
        """
        if not topic.get('active', True):
            return
            
        name = topic['name']
        print(f"\n📡 Scanning Target: {name}")
        
        # 1. Gather Targets from saved sources
        scan_queue = []
        
        # Refresh sources (optional, maybe once a day? For now, re-use or re-search)
        # For robustness, let's fast-check RSS feeds we already know
        known_rss = topic['sources'].get('rss', [])
        for feed in known_rss:
            print(f"   Reading Feed: {feed}")
            items = self.radar.scan_feed(feed)
            scan_queue.extend(items)
            
        # Also add static targets logic here if needed (re-checking static pages)
        known_static = topic['sources'].get('static', [])
        for static in known_static:
             scan_queue.append({'url': static, 'title': f"Static: {name}", 'published': "Today"})

        # 2. Sniper Execution (Batch)
        # Limit to 5 newest for efficiency per topic
        if not scan_queue:
            print("   No new signals found.")
            return
            
        batch_targets = scan_queue[:5]
        contents = []
        valid_targets = []
        
        print(f"   🎯 Sniping {len(batch_targets)} sources...")
        for t in batch_targets:
            sniper_result = await self.sniper._shoot_async(t['url'])
            if sniper_result and sniper_result.get("text"):
                contents.append(sniper_result["text"])
                if sniper_result.get("published_date"):
                    t['published'] = sniper_result["published_date"]
                valid_targets.append(t)
        
        # 3. Verification
        if contents:
            print(f"   🧠 Analyzing {len(contents)} documents for Alpha on '{name}'...")
            alphas = self.verifier.extract_alphas_batch(contents, topic_name=name)
            
            new_count = 0
            for item in alphas:
                alpha_text = item.get('text')
                src_idx = item.get('source_index')
                
                if alpha_text and src_idx is not None and 0 <= src_idx < len(valid_targets):
                    source_url = valid_targets[src_idx]['url']
                    published_date = valid_targets[src_idx].get('published', '')
                    
                    is_saved, final_fact = self.engine.process_extracted_alpha(alpha_text, source_url, published_date)
                    if is_saved:
                        new_count += 1
            
            print(f"   ✅ Cycle Complete. Found {new_count} new Alphas.")

if __name__ == "__main__":
    # Smoke Test
    manager = SurveillanceManager()
    asyncio.run(manager.run_cycle())
