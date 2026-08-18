import json
import sys

sys.path.insert(0, "apps/api")

from src.services.reasoning import extract_decision, evaluate_assumption


decision = """
We decided to host Atlas on Render because we expect fewer than
10,000 requests per day and want to keep infrastructure spending
below $100 per month.
"""

print("\n=== DECISION EXTRACTION ===")

result = extract_decision(decision)
print(json.dumps(result, indent=2))

assert result["assumptions"], "No assumptions extracted."

print("\n=== ASSUMPTION EVALUATION ===")

evaluation = evaluate_assumption(
    "Atlas traffic will remain below 10,000 requests per day.",
    "Atlas now receives 47,000 requests per day."
)

print(json.dumps(evaluation, indent=2))

assert evaluation["verdict"] in {
    "SUPPORTS",
    "WEAKENS",
    "CONTRADICTS",
    "INVALIDATES",
    "UNRELATED",
}

print("\n✅ AXIOM REASONING TEST PASSED")
