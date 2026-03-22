import google.generativeai as genai
import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class TruthAgent:
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("⚠️ WARNING: GOOGLE_API_KEY not found.")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)

    def verify(self, fact: str, source_text: str) -> bool:
        if not self.model: return False
        prompt = f"""
        Analyze if this FACT is supported by the SOURCE TEXT. 
        REJECT (NO) if it's navigational noise, UI, or SSL errors.
        FACT: "{fact}"
        SOURCE: "{source_text[:4000]}"
        Output ONLY 'YES' or 'NO'.
        """
        try:
            response = self.model.generate_content(prompt)
            return "YES" in response.text.strip().upper()
        except Exception as e:
            return False


    def extract_alphas(self, source_text: str) -> List[str]:
        if not self.model: return []
        prompt = f"""
        Extract the TOP 3 most important, novel facts (Alphas) from this text.
        Ignore all errors, nav-links, and technical noise.
        TEXT: "{source_text[:5000]}"
        Output format:
        ALPHA 1: [text]
        ALPHA 2: [text]
        ALPHA 3: [text]
        """
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            
            extracted = []
            # More robust parsing: find any line that starts with ALPHA
            lines = text.split("\n")
            for line in lines:
                if "ALPHA" in line.upper() and ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        extracted.append(parts[1].strip())
            
            return extracted
        except Exception as e:
            return []

    def extract_alphas_batch(self, contents: List[str], topic_name: str = "General") -> List[dict]:
        """
        Extracts Alphas from multiple articles in one go.
        Returns: [{'text': '...', 'source_index': 0}, ...]
        """
        if not self.model or not contents: return []
        
        # Build a "Digest" prompt
        digest = ""
        for i, text in enumerate(contents):
            # Safe slice
            safe_text = text[:50000] if len(text) > 50000 else text
            digest += f"--- ARTICLE {i} ---\n{safe_text}\n\n"

        prompt = f"""
        CRITICAL: You are an ELITE INTELLIGENCE ANALYST. Your goal is to produce a "CIA/Bloomberg Terminal" style brief.
        
        TOPIC: '{topic_name}'
        
        RULES OF ENGAGEMENT:
        1. **NOISE FILTER**: Ignore facts about celebrities, sports, or politics unless DIRECTLY impacting '{topic_name}'.
        2. **METRIC PRESERVATION**: If the text contains a specific Number, Date, Price, or Percentage, you MUST quote it exactly. ONE DO NOT SUMMARIZE METRICS.
           - BAD: "Aramco cut production significantly."
           - GOOD: "Aramco cut blue ammonia targets from **11M tons** to **2.5M tons** (-77%)."
        3. **STYLE**: Dense, telegraphic sentences. No filler words ("The company announced...").
           - BAD: "It is reported that TSMC might be delaying..."
           - GOOD: "TSMC Arizona 4nm volume production delayed to **2025**."
        4. **CONFLICT DETECTION**: If Source A says 'Active' and Source B says 'Cancelled', explicitly report the conflict.
           - "CONFLICT: Source 0 claims X, while Source 1 reports Y."
        
        Analyze these {len(contents)} articles.
        Extract the TOP 5 most critical Alphas about '{topic_name}'.
        
        TEXTS:
        {digest}
        
        Output format:
        ALPHA: [Dense Fact Text] | PRECISE_SOURCE_ID: [Article Number 0-{len(contents)-1}]
        """
        
        try:
            # Explicitly assigning response
            response = self.model.generate_content(prompt)
            
            # Robust Printing
            if hasattr(response, 'text'):
                print(f"🔍 RAW LLM OUTPUT START:\n{response.text}\n🔍 RAW LLM OUTPUT END", flush=True)
                lines = response.text.strip().split("\n")
            else:
                print(f"❌ RAW LLM OUTPUT MISSING TEXT. Response: {response}", flush=True)
                return []
            
            results = []
            for line in lines:
                if "ALPHA:" in line and "SOURCE_ID:" in line:
                    try:
                        # Parse: ALPHA: [Text] | PRECISE_SOURCE_ID: [ID]
                        parts = line.split("|")
                        fact = parts[0].split("ALPHA:", 1)[1].strip()
                        src_id_str = parts[1].split("SOURCE_ID:", 1)[1].strip()
                        # Extract just digits
                        import re
                        digits = re.findall(r'\d+', src_id_str)
                        if not digits: continue
                        src_id = int(digits[0])
                        results.append({"text": fact, "source_index": src_id})
                    except:
                        continue
            
            # --- LAYER 2: CROSS-EXAMINATION (CONFLICT CHECK) ---
            if len(results) > 1:
                conflicts = self.cross_examine(results)
                results.extend(conflicts)
                
            return results
            
        except Exception as e:
            print(f"❌ Verifier Error in extract_alphas_batch: {e}", flush=True)
            return []

    def cross_examine(self, alphas: List[dict]) -> List[dict]:
        """
        Layer 2: Checks a list of Alphas for mutual contradictions.
        Returns a list of CONFLICT Alphas.
        """
        if not self.model or len(alphas) < 2: return []
        
        # Prepare the dossier
        dossier = ""
        for i, alpha in enumerate(alphas):
            dossier += f"FACT {i}: {alpha['text']} (Source ID: {alpha['source_index']})\n"
            
        prompt = f"""
        CRITICAL: CROSS-EXAMINATION PROTOCOL
        
        You are a hostile Fact-Checker. Your goal is to find CONTRADICTIONS in this list of facts.
        Look for:
        1. Conflicting Dates (e.g., "Delayed to 2026" vs "Profitable in 2025").
        2. Conflicting Numbers (e.g., "$10B cost" vs "$65B cost").
        3. Conflicting Status (e.g., "Cancelled" vs "Moving Forward").
        
        FACTS:
        {dossier}
        
        If you find a contradiction, output it in this format:
        CONFLICT: [Description of conflict] | SOURCE_IDS: [ID1, ID2]
        
        If no conflicts exist, output NOTHING.
        """
        
        try:
            response = self.model.generate_content(prompt)
            new_conflicts = []
            if hasattr(response, 'text'):
                lines = response.text.strip().split("\n")
                for line in lines:
                    if "CONFLICT:" in line:
                        parts = line.split("|")
                        text = parts[0].replace("CONFLICT:", "").strip()
                        # We attribute the conflict to the first source involved, just for data structure
                        # But the text itself explains the conflict.
                        # We try to parse SOURCE_IDS to pick a representative ID
                        src_id = alphas[0]['source_index'] # Default
                        try:
                            s_part = parts[1]
                            digits = [int(s) for s in re.findall(r'\d+', s_part)]
                            if digits: src_id = digits[0]
                        except:
                            pass
                            
                        new_conflicts.append({
                            "text": f"⚠️ CONFLICT DETECTED: {text}",
                            "source_index": src_id 
                        })
            return new_conflicts

        except Exception as e:
            print(f"❌ Cross-Examination Error: {e}")
            return []



