import asyncio
from truebrief.sniper import Sniper
from truebrief.verifier import TruthAgent

async def debug_extraction():
    url = "https://techcrunch.com/2026/01/31/nvidia-ceo-pushes-back-on-reports-his-companys-100b-openai-investment-has-stalled/"
    
    print(f"🎯 Sniping: {url}", flush=True)
    sniper = Sniper()
    content = await sniper._shoot_async(url)
    
    if not content:
        print("❌ Sniper failed to get content.", flush=True)
        return

    print(f"📄 Content Length: {len(content)}", flush=True)
    print(f"📄 Preview: {content[:500]}...", flush=True)
    
    print("\n🧠 Verifying...", flush=True)
    verifier = TruthAgent()
    # Mocking the batch input format
    batch = [content]
    
    # We want to see the RAW output from Gemini if possible, 
    # but the method `extract_alphas_batch` parses it.
    # Let's call the internal generation method if it exists, or just run the public one and print result.
    
    results = verifier.extract_alphas_batch(batch)
    print("\n🔍 Extraction Results:")
    print(results)

if __name__ == "__main__":
    asyncio.run(debug_extraction())
