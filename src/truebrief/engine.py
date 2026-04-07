from typing import List, Tuple
from .memory import FactLedger
from .verifier import TruthAgent

# --- Configuration ---
# SIMILARITY_THRESHOLD is now handled inside FactLedger

class Atomizer:
    """
    Responsibilities:
    1. Cleaning text.
    2. Splitting into atomic sentences (Clause-based).
    """
    def __init__(self):
        # Load small English model for sentence splitting
        import spacy
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Downloading spacy model 'en_core_web_sm'...")
            from spacy.cli import download
            download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

    def atomize(self, text: str) -> List[str]:
        # Intelligent Noise Blacklist
        NOISE_TERMS = [
            "privacy policy", "terms of use", "cookies", "about us", "contact us",
            "dmca", "copyright", "all rights reserved", "follow us", "subscribe",
            "back to previous", "site blocked", "cyberguard", "לא בטוח"
        ]
        
        doc = self.nlp(text)
        final_atoms = []
        for sent in doc.sents:
            text_lower = sent.text.lower()
            
            # 1. Skip if noise term detected
            if any(noise in text_lower for noise in NOISE_TERMS):
                continue
                
            # 2. Skip if it looks like a lone URL or image reference
            if text_lower.startswith("[") and text_lower.endswith("]"):
                continue

            clauses = self._split_clauses(sent)
            final_atoms.extend(clauses)
        
        # 3. Filter short fragments (< 30 chars for quality)
        return [a.strip() for a in final_atoms if len(a.strip()) > 30]


    def _split_clauses(self, sent_span) -> List[str]:
        splits = []
        last_start = sent_span.start
        for token in sent_span:
            should_split = False
            if token.text.lower() in ['and', 'but', 'however']:
                head = token.head
                if head.pos_ in ['VERB', 'AUX']:
                    if head.dep_ == 'conj':
                        should_split = True
                    else:
                        has_conj_sibling = any(
                            child.dep_ == 'conj' and child.i > token.i 
                            for child in head.children
                        )
                        if has_conj_sibling:
                            should_split = True
            elif token.text == ';':
                should_split = True

            if should_split:
                 span = sent_span.doc[last_start : token.i]
                 splits.append(span.text)
                 last_start = token.i + 1

        span = sent_span.doc[last_start : sent_span.end]
        splits.append(span.text)
        return splits

class NoveltyFilter:
    """
    The Orchestrator. 
    It checks Memory for novelty AND calls the Verifier to ensure truth.
    """
    def __init__(self, memory: FactLedger = None):
        self.memory = memory if memory else FactLedger()
        self.verifier = TruthAgent()


    def analyze(self, fact: str, source_text: str) -> Tuple[bool, str]:
        """
        Deep analysis of a fact.
        Returns: (is_alpha, reason)
        """
        # 1. Semantic Novelty Check (Vector Search)
        is_novel, score, match_payload = self.memory.is_novel(fact)
        
        if not is_novel:
            match_text = match_payload.get("text", "") if match_payload else ""
            return False, f"Duplicate of: '{match_text[:50]}...'"

        # 2. Verification Check (LLM Grounding)
        is_true = self.verifier.verify(fact, source_text)
        
        if not is_true:
            return False, "Unverified/Hallucination"

        return True, "Alpha Found"

    def commit(self, fact: str, source_url: str, published_date: str = "", topic_name: str = ""):
        """Saves a verified alpha to memory."""
        self.memory.add_fact(fact, source_url, published_date, topic_name)

    def process_extracted_alpha(self, alpha_text: str, source_url: str, published_date: str = "", topic_name: str = "") -> Tuple[bool, str]:
        """
        Processes an extracted alpha through the Time Detective if it collides in Memory.
        Returns (is_saved, final_fact_text)
        """
        is_novel, score, match_payload = self.memory.is_novel(alpha_text, topic_name=topic_name)
        
        if is_novel:
            self.commit(alpha_text, source_url, published_date, topic_name)
            return True, alpha_text
            
        # Collision! Invoke Time Detective
        if not hasattr(self, 'time_detective'):
            from .context_verifier import TimeDetective
            self.time_detective = TimeDetective()
            
        decision, hist_box, new_box, delta_alpha = self.time_detective.evaluate(alpha_text, published_date, match_payload)
        
        # Mathematical date overlap logic
        if decision in ["UPDATE", "NEW_EVENT"] and delta_alpha and delta_alpha.lower() != "none":
         # 3. Safe Parsing and Temporal Math
            try:
                old_start = datetime.strptime(match_payload.get('start_date', '1970-01-01'), "%Y-%m-%d")
                old_end = datetime.strptime(match_payload.get('end_date', '1970-01-01'), "%Y-%m-%d")
                
                new_start = datetime.strptime(new_box['start_date'], "%Y-%m-%d")
                new_end = datetime.strptime(new_box['end_date'], "%Y-%m-%d")
                
                print(f"   [Math Engine] Evaluating Overlap:")
                print(f"      History Box: {old_start.strftime('%Y-%m-%d')} to {old_end.strftime('%Y-%m-%d')}")
                print(f"      New Box    : {new_start.strftime('%Y-%m-%d')} to {new_end.strftime('%Y-%m-%d')}")
                
                # --- MISSION 7.2 FIX: Breaking News Safety ---
                # If the new fact advances the temporal horizon into the future, 
                # it is inherently an UPDATE, regardless of how much historical overlap exists.
                if new_end > old_end:
                    print(f"   ✅ Temporal Horizon Advanced. Approving LLM UPDATE.")
                else:
                    # Calculate Intersection
                    latest_start = max(old_start, new_start)
                    earliest_end = min(old_end, new_end)
                    delta = (earliest_end - latest_start).days
                    
                    if delta > 0:
                        overlap_ratio = delta / max(1, (new_end - new_start).days)
                        if overlap_ratio >= 0.8:
                            print(f"   ⚠️ Mathematical Overlap Detected. Overruling LLM UPDATE -> DUPLICATE.")
                            decision = "DUPLICATE" # Update decision variable to reflect math engine override
                
            except Exception as e:
                print(f"   ⚠️ Math Engine failed to parse dates: {e}")
            
            if decision == "DUPLICATE": # Check the updated decision after math engine
                return False, alpha_text

            human_readable_date = new_box.get("human_readable", published_date)
            # Memory expects published_date as a string, we pass human_readable
            self.commit(delta_alpha, source_url, human_readable_date, topic_name)
            return True, delta_alpha
            
        return False, alpha_text
