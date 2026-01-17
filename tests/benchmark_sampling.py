from truebrief.engine import Atomizer, NoveltyFilter
import os

def run_benchmark():
    with open("data/simulated_news.txt", "r") as f:
        content = f.read()

    atomizer = Atomizer()
    filter = NoveltyFilter()
    
    atoms = atomizer.atomize(content)
    print(f"Total Atoms found: {len(atoms)}")

    print("\n--- TEST A: Sampling[:10] ---")
    alphas_a = []
    for a in atoms[:10]:
        is_alpha, _ = filter.analyze(a, content)
        if is_alpha: alphas_a.append(a)
    print(f"Sampling Results ({len(alphas_a)}):")
    for a in alphas_a: print(f"  - {a}")

    print("\n--- TEST B: Full Article ---")
    alphas_b = []
    for a in atoms:
        is_alpha, _ = filter.analyze(a, content)
        if is_alpha: alphas_b.append(a)
    print(f"Full Scan Results ({len(alphas_b)}):")
    for a in alphas_b: print(f"  - {a}")

    print(f"\nCONCLUSION: Sampling caught {len(alphas_a)}/{len(alphas_b)} Alphas.")

if __name__ == "__main__":
    run_benchmark()
