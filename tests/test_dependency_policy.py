import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_dependencies import audit


def distribution(requires=(), extras=()):
    metadata = Message()
    for extra in extras:
        metadata["Provides-Extra"] = extra
    return SimpleNamespace(version="1.0", requires=list(requires), metadata=metadata)


class DependencyPolicyTests(unittest.TestCase):
    def test_model_dependency_hidden_behind_extra_is_rejected(self):
        graph = {"root": distribution(['helper; extra == "pdf"'], ["pdf"]),
                 "helper": distribution(["torch>=2"])}
        with patch("audit_dependencies.metadata.distribution", graph.__getitem__):
            result = audit(["root[pdf]==1.0"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["issues"][0]["code"], "forbidden_dependency")
        self.assertEqual(result["issues"][0]["parent"], "helper")

    def test_unselected_model_extra_does_not_enter_closure(self):
        with patch("audit_dependencies.metadata.distribution", return_value=distribution(['torch; extra == "models"'], ["models"])):
            result = audit(["root==1.0"])
        self.assertTrue(result["passed"])
        self.assertNotIn("torch", result["packages"])

    def test_unknown_extra_and_version_mismatch_are_not_accepted(self):
        with patch("audit_dependencies.metadata.distribution", return_value=distribution()):
            result = audit(["root[missing]==2.0"])
        self.assertEqual({i["code"] for i in result["issues"]}, {"unknown_extra", "version_mismatch"})


if __name__ == "__main__":
    unittest.main()
