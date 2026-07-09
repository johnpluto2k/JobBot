"""Seniority level classifier evaluation.

Measures accuracy of job_bot.seniority.classify() against a hand-labeled eval set.
Identifies false-keeps (senior jobs that survive the KEEP_MAX threshold).
"""

import json
from pathlib import Path
from collections import defaultdict

import pytest
from job_bot.seniority import classify

# Load eval set from fixtures
EVAL_SET_PATH = Path(__file__).parent / "fixtures" / "seniority_eval.jsonl"


def load_eval_set():
    """Load eval set from JSONL file, skip comment lines."""
    data = []
    with open(EVAL_SET_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return data


class TestSeniorityClassification:
    """Test seniority classifier accuracy."""

    @pytest.fixture
    def eval_data(self):
        return load_eval_set()

    def test_accuracy(self, eval_data):
        """Measure overall accuracy across eval set."""
        if not eval_data:
            pytest.skip("Eval set is empty")

        results = []
        correct = 0
        for item in eval_data:
            title = item["title"]
            expected_level = item["expected_level"]
            reason = item.get("reason", "")

            # Call classifier
            predicted_level = classify(title)

            match = predicted_level == expected_level
            if match:
                correct += 1

            results.append({
                "title": title,
                "expected": expected_level,
                "predicted": predicted_level,
                "match": match,
                "reason": reason,
            })

        accuracy = correct / len(eval_data)
        print(f"\n\nSeniority Classifier Accuracy: {accuracy:.1%} ({correct}/{len(eval_data)})")

        # Report mismatches
        mismatches = [r for r in results if not r["match"]]
        if mismatches:
            print(f"\nMisclassifications ({len(mismatches)}):")
            for m in mismatches:
                print(
                    f"  {m['title']!r}: expected {m['expected']}, got {m['predicted']} "
                    f"({m['reason']})"
                )

        # Check for false-keeps (senior roles classified as entry/mid)
        false_keeps = [
            r
            for r in results
            if r["expected"] in ("senior", "lead", "exec")
            and r["predicted"] in ("entry", "mid")
        ]
        if false_keeps:
            print(f"\nFalse-Keeps (senior job kept as lower level: {len(false_keeps)}):")
            for m in false_keeps:
                print(f"  {m['title']!r}: expected {m['expected']}, got {m['predicted']}")

        # Hard constraint: accuracy >= 80%
        assert accuracy >= 0.80, f"Accuracy {accuracy:.1%} below 80% threshold"

        # Hard constraint: no false-keeps on hard cases
        hard_case_titles = ["Associate Director", "Analyst III", "Staff Accountant"]
        hard_mismatches = [r for r in results if r["title"] in hard_case_titles and not r["match"]]
        assert not hard_mismatches, f"Hard cases failed: {hard_mismatches}"

    def test_false_keep_rate(self, eval_data):
        """Measure false-keep rate (senior roles kept as entry/mid)."""
        results = []
        for item in eval_data:
            title = item["title"]
            expected_level = item["expected_level"]
            predicted_level = classify(title)

            is_false_keep = (
                expected_level in ("senior", "lead", "exec")
                and predicted_level in ("entry", "mid")
            )
            results.append(is_false_keep)

        false_keep_rate = sum(results) / len(results) if results else 0
        print(f"\n\nFalse-Keep Rate: {false_keep_rate:.1%}")

        # Hard constraint: false-keep rate <= 5%
        assert false_keep_rate <= 0.05, f"False-keep rate {false_keep_rate:.1%} exceeds 5%"


if __name__ == "__main__":
    # Run eval manually
    data = load_eval_set()
    print(f"Loaded {len(data)} eval cases")

    results = []
    correct = 0
    for item in data:
        title = item["title"]
        expected = item["expected_level"]
        predicted = classify(title)
        match = predicted == expected
        if match:
            correct += 1
        results.append((title, expected, predicted, match))

    accuracy = correct / len(data)
    print(f"\nAccuracy: {accuracy:.1%} ({correct}/{len(data)})")

    # Show mismatches
    mismatches = [(t, e, p) for t, e, p, m in results if not m]
    if mismatches:
        print(f"\nMismatches ({len(mismatches)}):")
        for title, expected, predicted in mismatches:
            print(f"  {title!r}: expected {expected}, got {predicted}")
