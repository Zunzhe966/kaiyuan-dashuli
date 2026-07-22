import unittest

from scripts.validate_research_worker_diff import (
    validate_changed_files,
    validate_commit_batches,
)


ALLOWED_GLOBS = [
    "data/quarantine/research/*.jsonl",
    "data/quarantine/research/*.manifest.json",
]


class ValidateResearchWorkerDiffTests(unittest.TestCase):
    def test_accepts_one_added_artifact_and_matching_manifest(self):
        changed = [
            ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("A", "data/quarantine/research/github-since-0-0001.manifest.json"),
        ]
        errors, pairs = validate_changed_files(
            changed,
            "data/research-20260722-github-since-0-0001",
            ALLOWED_GLOBS,
        )
        self.assertEqual(errors, [])
        self.assertEqual(pairs, [tuple(path for _, path in changed)])

    def test_rejects_non_data_branch(self):
        changed = [
            ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("A", "data/quarantine/research/github-since-0-0001.manifest.json"),
        ]
        errors, _ = validate_changed_files(changed, "feature/site", ALLOWED_GLOBS)
        self.assertTrue(any("branch" in error for error in errors), errors)

    def test_rejects_any_file_outside_worker_allowlist(self):
        changed = [
            ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("A", "data/quarantine/research/github-since-0-0001.manifest.json"),
            ("M", "site_src/app.js"),
        ]
        errors, _ = validate_changed_files(
            changed,
            "data/research-20260722-github-since-0-0001",
            ALLOWED_GLOBS,
        )
        self.assertTrue(any("outside worker allowlist" in error for error in errors), errors)

    def test_rejects_modifying_an_existing_batch(self):
        changed = [
            ("M", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("M", "data/quarantine/research/github-since-0-0001.manifest.json"),
        ]
        errors, _ = validate_changed_files(
            changed,
            "data/research-20260722-github-since-0-0001",
            ALLOWED_GLOBS,
        )
        self.assertTrue(any("new files" in error for error in errors), errors)

    def test_accepts_multiple_immutable_batches_in_one_accumulation_pr(self):
        changed = [
            ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("A", "data/quarantine/research/github-since-0-0001.manifest.json"),
            ("A", "data/quarantine/research/github-since-1-0002.jsonl"),
            ("A", "data/quarantine/research/github-since-1-0002.manifest.json"),
        ]
        errors, pairs = validate_changed_files(
            changed,
            "data/research-20260722-github-since-0-0001",
            ALLOWED_GLOBS,
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            pairs,
            [
                (
                    "data/quarantine/research/github-since-0-0001.jsonl",
                    "data/quarantine/research/github-since-0-0001.manifest.json",
                ),
                (
                    "data/quarantine/research/github-since-1-0002.jsonl",
                    "data/quarantine/research/github-since-1-0002.manifest.json",
                ),
            ],
        )

    def test_rejects_commit_that_adds_more_than_one_batch(self):
        commits = [
            (
                "data: research batch combined",
                [
                    ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
                    ("A", "data/quarantine/research/github-since-0-0001.manifest.json"),
                    ("A", "data/quarantine/research/github-since-1-0002.jsonl"),
                    ("A", "data/quarantine/research/github-since-1-0002.manifest.json"),
                ],
            )
        ]
        errors, _ = validate_commit_batches(commits, ALLOWED_GLOBS)
        self.assertTrue(any("one batch pair" in error for error in errors), errors)

    def test_rejects_commit_subject_that_does_not_name_its_batch(self):
        commits = [
            (
                "data: research batch wrong-id",
                [
                    ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
                    ("A", "data/quarantine/research/github-since-0-0001.manifest.json"),
                ],
            )
        ]
        errors, _ = validate_commit_batches(commits, ALLOWED_GLOBS)
        self.assertTrue(any("subject must be" in error for error in errors), errors)

    def test_rejects_mismatched_batch_filenames(self):
        changed = [
            ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("A", "data/quarantine/research/github-since-1-0002.manifest.json"),
        ]
        errors, _ = validate_changed_files(
            changed,
            "data/research-20260722-github-since-0-0001",
            ALLOWED_GLOBS,
        )
        self.assertTrue(any("one JSONL artifact and one manifest" in error for error in errors), errors)

    def test_rejects_nested_batch_path(self):
        changed = [
            ("A", "data/quarantine/research/github-since-0-0001.jsonl"),
            ("A", "data/quarantine/research/nested/github-since-0-0001.manifest.json"),
        ]
        errors, _ = validate_changed_files(
            changed,
            "data/research-20260722-github-since-0-0001",
            ALLOWED_GLOBS,
        )
        self.assertTrue(any("outside worker allowlist" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
