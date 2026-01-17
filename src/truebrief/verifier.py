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
