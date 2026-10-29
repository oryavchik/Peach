import unittest

from tf_plan_guard import check_plan


def plan(actions=None, importing=False, resources=1):
    return {
        "planned_values": {"root_module": {"resources": [
            {"mode": "managed"} for _ in range(resources)
        ]}},
        "resource_changes": [{
            "mode": "managed", "address": "aws_cognito_user_pool.main",
            "change": {"actions": actions or ["no-op"],
                       **({"importing": {"id": "existing"}} if importing else {})},
        }],
    }


class GuardTests(unittest.TestCase):
    def test_import_only(self):
        self.assertEqual(check_plan(plan(importing=True), "import-only", 1, 1)["imports"], 1)

    def test_replacement_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "delete/create"):
            check_plan(plan(["delete", "create"]), "import-only", 1, 1)

    def test_update_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "update"):
            check_plan(plan(["update"]), "import-only", 1, 1)

    def test_empty_plan_cannot_fake_coverage(self):
        with self.assertRaisesRegex(ValueError, "coverage"):
            check_plan(plan(resources=0), "no-changes", 40, 0)

    def test_unfinished_import_is_not_no_changes(self):
        with self.assertRaisesRegex(ValueError, "not yet completed"):
            check_plan(plan(importing=True), "no-changes", 1, 0)

    def test_final_noop(self):
        self.assertEqual(check_plan(plan(), "no-changes", 1, 0)["cloud_mutations"], 0)


if __name__ == "__main__":
    unittest.main()
