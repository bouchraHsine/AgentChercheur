from core.orchestrator import Orchestrator

if __name__ == "__main__":
    topic = input("Donne le sujet scientifique: ").strip()
    orch = Orchestrator()
    result = orch.run(topic=topic, results_per_query=15, final_k=3, required_keywords=[], strict_filter=True)
    print("OK. Fichiers générés dans outputs/:")
    print("- articles.json")
    print("- analyses.json")
    print("- comparison.md")
    print("- hypotheses.md")
    print("- experiments.md")
    print("- report.md")
