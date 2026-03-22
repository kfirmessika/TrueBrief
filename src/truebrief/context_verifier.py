import google.generativeai as genai
import os
from typing import Dict, Tuple

class TimeDetective:
    """
    The Time Detective (Mission 3.0).
    Resolves "Semantic Collisions" by looking at the Time Context.
    """
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("⚠️ WARNING: GOOGLE_API_KEY not found.")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)

    def evaluate(self, new_fact: str, new_date: str, history_payload: dict) -> Tuple[str, str, str]:
        """
        Evaluates a semantic collision.
        Returns: (Decision, EventDate, DeltaAlphaText)
        Decision is one of: ["DUPLICATE", "UPDATE", "NEW_EVENT"]
        """
        if not self.model: return "DUPLICATE", "", ""

        old_fact = history_payload.get("text", "Unknown Old Fact")
        old_date = history_payload.get("published_date", "Unknown Date")

        import datetime
        current_date_str = datetime.datetime.now().strftime("%B %d, %Y")

        prompt = f"""
        CRITICAL: TEMPORAL ANALYSIS PROTOCOL

        You are the Time Detective. Your job is to analyze two facts that sound similar and determine if they describe the EXACT SAME historical event (A Recitation) or a NEW DEVELOPMENT (An Update).
        TODAY'S SYSTEM DATE: {current_date_str}. Use this to calculate relative terms like "next 2 weeks".

        HISTORY FACT (Known):
        Text: "{old_fact}"
        Published On: {old_date}

        NEW REPORT (Just Discovered):
        Text: "{new_fact}"
        Published On: {new_date}

        ANALYSIS CRITERIA:
        1. Look at the numbers, dates, and actions. 
        2. If the New Report is just repeating the History Fact, or the event timeframes heavily overlap, it is a DUPLICATE.
        3. If the New Report has new numbers, or confirms an old rumor as a reality today, it is an UPDATE.
        4. If the New Report is a completely separate event that just sounds similar, it is a NEW_EVENT.

        OUTPUT FORMAT MUST BE STRICT VALID JSON:
        {{
            "decision": "DUPLICATE | UPDATE | NEW_EVENT",
            "history_bounding_box": {{
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD"
            }},
            "new_bounding_box": {{
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD",
                "human_readable": "Original phrasing (e.g., Q3 2025)"
            }},
            "delta_alpha": "If UPDATE or NEW_EVENT, write a dense, 1-sentence Alpha highlighting the CHANGE from the old fact. If DUPLICATE, write 'null'."
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            # Find JSON block
            import json, re
            text = response.text
            match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if match:
                text = match.group(1)
            else:
                match = re.search(r"({.*})", text, re.DOTALL)
                if match:
                    text = match.group(1)
            
            data = json.loads(text)
            
            decision = data.get("decision", "DUPLICATE")
            if decision not in ["DUPLICATE", "UPDATE", "NEW_EVENT"]:
                decision = "DUPLICATE"
                
            history_box = data.get("history_bounding_box", {})
            new_box = data.get("new_bounding_box", {})
            
            delta_alpha = data.get("delta_alpha", "")
            if str(delta_alpha).lower() == "null" or delta_alpha is None:
                delta_alpha = ""

            return decision, history_box, new_box, delta_alpha

        except Exception as e:
            print(f"❌ Time Detective Error: {e}")
            return "DUPLICATE", "", ""
