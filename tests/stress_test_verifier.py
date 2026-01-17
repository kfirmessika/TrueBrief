from truebrief.verifier import TruthAgent


def run_stress_test_verifier():
    print(f"{'='*10} QA STRESS TEST: VERIFIER {'='*10}")
    
    agent = TruthAgent()
    if not agent.model:
        print("⚠️ SKIPPING TESTS: No API Key.")
        return

    source_text = """
    Apple released the iPhone 15 on September 22, 2023. 
    It features a USB-C port, replacing the tailored Lightning connector.
    The Pro models use the new A17 Pro chip.
    """

    # Test 1: Explicit Support (YES)
    print("\n[Test 1] Explicit Support")
    fact_yes = "The iPhone 15 has a USB-C port."
    result = agent.verify(fact_yes, source_text)
    if result:
        print("✅ PASS: Correctly verified true fact.")
    else:
        print("❌ FAIL: Rejected true fact.")

    # Test 2: Explicit Contradiction/Absence (NO)
    print("\n[Test 2] fake Fact")
    fact_no = "The iPhone 15 uses the M3 chip."
    result = agent.verify(fact_no, source_text)
    if not result:
        print("✅ PASS: Correctly rejected false fact.")
    else:
        print("❌ FAIL: Hallucinated support for false fact.")

    # Test 3: Irrelevant Hallucination (NO)
    print("\n[Test 3] Irrelevant Fact")
    fact_irrelevant = "Bananas are yellow."
    result = agent.verify(fact_irrelevant, source_text)
    if not result:
        print("✅ PASS: Correctly rejected irrelevant fact.")
    else:
        print("❌ FAIL: Hallucinated support for irrelevant fact.")

if __name__ == "__main__":
    run_stress_test_verifier()
