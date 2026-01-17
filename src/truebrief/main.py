from .radar import Radar
from .sniper import Sniper
from .engine import Atomizer, NoveltyFilter

import time

def run_integration_pipeline():
    print(f"\n{'='*10} TRACER BULLET 3.0 (ALFA/NOISE PIPELINE) {'='*10}")
    
    # 1. Initialize Components
    radar = Radar()
    sniper = Sniper()
    atomizer = Atomizer()
    engine = NoveltyFilter()
    
    # 2. Run Radar
    feed_url = "http://feeds.feedburner.com/TechCrunch/"
    targets = radar.scan_feed(feed_url)
    
    # Limit to top 2 for testing speed
    targets = targets[:2] if targets else []
    
    print(f"\n--- Processing {len(targets)} Targets ---")
    
    for t in targets:
        print(f"\n[Target] {t['title']}")
        print(f"   URL: {t['url']}")
        
        # 3. Sniper (Extract)
        content = sniper.capture(t['url'])
        if not content:
            print("   ❌ Failed to capture content.")
            continue
            
        print(f"   ✅ Captured {len(content)} chars.")
        
        # 4. Atomize
        atoms = atomizer.atomize(content)
        print(f"   Note: Analyzing {len(atoms)} sentences...")
        
        # 5. Filter (Sample first 2 valid sentences)
        alpha_count = 0
        for i, sent in enumerate(atoms): 
            if alpha_count >= 2: break # Only show first 2 alphas per target for test
            
            is_alpha, reason = engine.analyze(sent, content)
            
            if is_alpha:
                print(f"      [ALPHA] {sent[:80]}...")
                engine.commit(sent, t['url'])
                alpha_count += 1
            else:
                print(f"      [NOISE] {sent[:60]}... -> {reason}")
            
if __name__ == "__main__":
    run_integration_pipeline()

