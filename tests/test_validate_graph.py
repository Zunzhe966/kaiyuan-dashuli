import tempfile
import unittest
from pathlib import Path

from scripts.validate_graph import validate_domain


class ValidateGraphTests(unittest.TestCase):
    def test_rejects_malformed_domain_index_yaml(self):
        with tempfile.TemporaryDirectory() as directory:
            domain = Path(directory) / "example"
            nodes = domain / "nodes"
            nodes.mkdir(parents=True)
            (nodes / "example.yaml").write_text(
                "\n".join(
                    (
                        "id: example",
                        "name: Example",
                        "repo: https://github.com/example/example",
                        "summary: Example",
                        "tags: [example]",
                        "status: active",
                        "use_when: Example",
                        "avoid_when: Example",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            (domain / "_index.yaml").write_text(
                "domain: example\n"
                "categories:\n"
                "  - id: broken\n"
                "      node_ids: [example]\n"
                "nodes_dir: nodes\n",
                encoding="utf-8",
            )

            errors = []
            validate_domain(domain, errors)

            self.assertTrue(any("invalid YAML" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
