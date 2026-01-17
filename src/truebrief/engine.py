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
        is_novel, score, match = self.memory.is_novel(fact)
        
        if not is_novel:
            return False, f"Duplicate of: '{match[:50]}...'"

        # 2. Verification Check (LLM Grounding)
        is_true = self.verifier.verify(fact, source_text)
        
        if not is_true:
            return False, "Unverified/Hallucination"

        return True, "Alpha Found"

    def commit(self, fact: str, source_url: str):
        """Saves a verified alpha to memory."""
        self.memory.add_fact(fact, source_url)
