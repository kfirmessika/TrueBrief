import feedparser
import time
from typing import List, Dict, Set

class Radar:
    """
    The Radar scans the horizon (RSS Feeds) for potential targets (URLs).
    It does NOT read the content. It just finds 'Where to look'.
    """
    def __init__(self):
        self.seen_urls: Set[str] = set() # Long-term memory logic needed later (DB)

    def scan_feed(self, feed_url: str) -> List[Dict]:
        """
        Polls a single feed and returns NEW items only.
        """
        print(f"📡 Radar scanning: {feed_url}...")
        
        try:
            feed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"❌ Radar Malfunction on {feed_url}: {e}")
            return []

        if hasattr(feed, 'bozo_exception') and feed.bozo_exception:
            # feedparser captures errors in 'bozo_exception'
            print(f"⚠️  Radar Warning: Malformed feed {feed_url}")
            # We continue anyway, as it often parses partial data

        new_targets = []
        
        if not feed.entries:
            print("   -> No signal (Empty Feed).")
            return []

        for entry in feed.entries:
            link = entry.get('link', '')
            title = entry.get('title', 'Unknown Title')
            
            if not link:
                continue

            if link in self.seen_urls:
                continue # Ignore old signals

            # Register as seen
            self.seen_urls.add(link)
            
            target = {
                "source": feed.feed.get('title', 'Unknown Source'),
                "title": title,
                "url": link,
                "published": entry.get('published', '')
            }
            new_targets.append(target)

        print(f"   -> Found {len(new_targets)} new targets.")
        return new_targets

if __name__ == "__main__":
    # Builder's Manual Test
    radar = Radar()
    # Test with a reliable tech feed
    targets = radar.scan_feed("http://feeds.feedburner.com/TechCrunch/")
    
    print("\n--- Targets Acquired ---")
    for t in targets[:3]: # Show first 3
        print(f"[{t['source']}] {t['title']}")
        print(f"   {t['url']}")
