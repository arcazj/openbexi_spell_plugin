"""Only the exact dedicated OBS runner may omit the shared-runner suite field."""
import unittest
from limit_report import ROOT, digest, matches_suite_identity


class RunnerIdentityTests(unittest.TestCase):
    def test_exact_dedicated_obs_identity_is_accepted_only_for_obs(self):
        report={'inputs':{'conformance/run_obs.py':digest(ROOT/'conformance/run_obs.py')}}
        self.assertTrue(matches_suite_identity(report,'obs'))
        self.assertFalse(matches_suite_identity(report,'limit'))

    def test_missing_or_wrong_runner_hash_is_rejected(self):
        for report in ({},{'inputs':{}},{'inputs':{'conformance/run_obs.py':'0'*64}}):
            with self.subTest(report=report):
                self.assertFalse(matches_suite_identity(report,'obs'))

    def test_explicit_wrong_or_null_suite_cannot_use_dedicated_fallback(self):
        for suite in ('limit',None,'other'):
            report={'suite':suite,'inputs':{'conformance/run_obs.py':digest(ROOT/'conformance/run_obs.py')}}
            with self.subTest(suite=suite):
                self.assertFalse(matches_suite_identity(report,'obs'))

    def test_existing_shared_runner_keeps_explicit_selection(self):
        self.assertTrue(matches_suite_identity({'suite':'obs'},'obs'))
        self.assertTrue(matches_suite_identity({'suite':'limit'},'limit'))
        self.assertFalse(matches_suite_identity({'suite':'obs'},'limit'))


if __name__=='__main__':
    unittest.main()
