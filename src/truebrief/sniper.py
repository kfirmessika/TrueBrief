import asyncio
import sys
from crawl4ai import AsyncWebCrawler
from typing import Optional, Dict
from bs4 import BeautifulSoup

# Reverted Windows Loop Policy (Breaks Playwright)



class Sniper:
    """
    The Sniper visits a specific URL and extracts clean Markdown.
    It uses a Headless Browser (Crawl4AI) to render JS and bypass basic anti-bot.
    """
    def __init__(self):
        pass

    async def _shoot_async(self, url: str) -> Optional[Dict[str, str]]:
        """Async core using Crawl4AI with Stealth/Bypass options."""
        print(f"🎯 Sniper targeting: {url}")
        try:
            async with AsyncWebCrawler(verbose=True) as crawler:
                # We ignore HTTPS errors to bypass local ISP blocks/CyberGuard intercepts
                result = await crawler.arun(
                    url=url,
                    ignore_https_errors=True,
                    js_code="window.scrollTo(0, document.body.scrollHeight);",
                    delay_before_return_html=2.0
                )
                if result.success:
                    # Basic cleaning (heuristic)
                    markdown = str(result.markdown)
                    if len(markdown) < 100:
                        print(f"⚠️  Target empty or too small ({len(markdown)} chars).")
                        return None # Return None if too small
                        
                    published_date = ""
                    try:
                        if hasattr(result, 'html') and result.html:
                            soup = BeautifulSoup(result.html, 'html.parser')
                            meta_date = soup.find('meta', property='article:published_time')
                            if meta_date and meta_date.get('content'):
                                published_date = meta_date['content']
                            else:
                                meta_pub = soup.find('meta', attrs={'name': 'pubdate'})
                                if meta_pub and meta_pub.get('content'):
                                    published_date = meta_pub['content']
                                else:
                                    time_tag = soup.find('time')
                                    if time_tag and time_tag.has_attr('datetime'):
                                        published_date = time_tag['datetime']
                    except Exception as e:
                        print(f"   ⚠️ Date extraction failed: {e}")
                        
                    print(f"   -> Hit! Extracted {len(markdown)} chars. Date: {published_date}")
                    return {"text": markdown, "published_date": published_date}
                else:
                    print(f"❌ Missed shot on {url}: {result.error_message}")
                    return None

        except Exception as e:
            print(f"❌ Sniper Rifle Jammed: {e}")
            return None

    def capture(self, url: str) -> Optional[Dict[str, str]]:
        """
        Synchronous wrapper for the async shot.
        """
        return asyncio.run(self._shoot_async(url))

if __name__ == "__main__":
    # Builder's Manual Test
    sniper = Sniper()
    # Test on a real article (using a stable URL logic or hardcoded for test)
    # Using a Wikipedia page as a stable target
    txt = sniper.capture("https://en.wikipedia.org/wiki/Artificial_intelligence")
    
    if txt:
        print("\n--- Preview ---")
        print(txt[:500]) # First 500 chars
