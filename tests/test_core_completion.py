#!/usr/bin/env python3
"""Deterministic regression checks for TOSEM core-completion outputs."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FS = ROOT / "results" / "derived" / "full_study"
CC = FS / "core_completion"


class TestCoreCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.primary = json.loads((FS / "primary_summary.json").read_text())
        cls.summary = json.loads((CC / "summary.json").read_text())

    def test_primary_unchanged(self):
        p = self.summary["primary_unchanged"]
        self.assertEqual(p["n"], 288)
        self.assertAlmostEqual(p["excess"], self.primary["excess"], places=12)
        self.assertAlmostEqual(p["r_trigger"], self.primary["r_trigger"], places=12)
        self.assertAlmostEqual(p["r_placebo"], self.primary["r_placebo"], places=12)

    def test_timeout_only_positive(self):
        to = self.summary["timeout_only"]
        self.assertEqual(to["n"], 288)
        self.assertGreater(to["mean"], 0.3)
        self.assertLess(to["ci95"][0], to["mean"])
        self.assertGreater(to["ci95"][1], to["mean"])

    def test_single_trigger_preserves_direction(self):
        st = self.summary["single_trigger"]
        self.assertEqual(st["n"], 194)
        self.assertGreater(st["mean"], 0.0)
        self.assertGreater(st["ci95"][0], 0.0)

    def test_tipping_points(self):
        tip = self.summary["tipping_point"]
        self.assertAlmostEqual(tip["convention_A_required_mean_excess"], -0.32640782188299855, places=8)
        self.assertEqual(tip["convention_B_projected_primary_missing_n"], 223)
        self.assertAlmostEqual(tip["convention_B_required_mean_excess"], -0.5459646527460021, places=8)

    def test_taxonomy_partitions_266(self):
        tax = self.summary["mutation_failure_taxonomy"]
        self.assertEqual(tax["n"], 266)
        self.assertEqual(sum(tax["counts"].values()), 266)
        self.assertEqual(tax["unknown"], 0)

    def test_historical_481(self):
        h = self.summary["historical_fault_level"]
        self.assertEqual(h["n_evaluable"], 481)
        self.assertEqual(h["n_coupled"], 385)

    def test_figures_exist(self):
        self.assertTrue((CC / "figures" / "fig_project_forest.png").is_file())
        self.assertTrue((CC / "figures" / "fig_rq1_paired_rates_jitter.png").is_file())


if __name__ == "__main__":
    unittest.main()
