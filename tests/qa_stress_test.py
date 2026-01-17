import spacy
from truebrief.engine import Atomizer
  # Import the class we are testing

# --- TESTER'S SUITE ---
# Goal: Break the "Clause Splitting" logic.

test_cases = [
    {
        "type": "Standard Compound",
        "input": "The market crashed and I lost money.",
        "expected": 2
    },
    {
        "type": "List (Oxford Comma)",
        "input": "I bought apples, oranges, and pears.",
        "expected": 1, # Should NOT split a list
        "note": "Builder's logic might mistake list 'and' for clause 'and'."
    },
    {
        "type": "Quote Protection",
        "input": "He said 'up and down' and left the room.",
        "expected": 2, # Should split main clause, but NOT inside the quote
        "note": "Can Spacy distinguish 'and' inside quotes?"
    },
    {
        "type": "Complex But",
        "input": "I wanted to go but simply could not find the time.",
        "expected": 2 # 'could not find' is a verb phrase, should split?
    },
    {
        "type": "False Positive 'And'",
        "input": "The quick and brown fox jumped.",
        "expected": 1 # Adjective connector, not clause connector.
    }
]

def run_stress_test():
    print(f"{'='*10} QA STRESS TEST: ATOMIZER {'='*10}")
    atomizer = Atomizer()
    
    failures = 0
    for case in test_cases:
        print(f"\n[Test Type]: {case['type']}")
        print(f"Input: '{case['input']}'")
        
        atoms = atomizer.atomize(case['input'])
        count = len(atoms)
        
        print(f"Result Atoms: {atoms}")
        
        if count == case['expected']:
            print(f"✅ PASS")
        else:
            print(f"❌ FAIL (Expected {case['expected']}, got {count})")
            if "note" in case:
                print(f"   NOTE: {case['note']}")
            failures += 1

    print(f"\n{'-'*30}")
    print(f"Total Failures: {failures} / {len(test_cases)}")

if __name__ == "__main__":
    run_stress_test()
