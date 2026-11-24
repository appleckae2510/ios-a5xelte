import importlib.util
import pathlib
import tempfile
import unittest

p = pathlib.Path(__file__).resolve().parents[1] / "tools" / "a3_j3_compat.py"
spec = importlib.util.spec_from_file_location("a3_j3_compat", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class MergeTests(unittest.TestCase):
    def test_apply_and_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for rel, old, new in m.CHANGES:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a") as f:
                    f.write(old + "\n")
            m.apply(root)
            m.apply(root)
            for rel, old, new in m.CHANGES:
                self.assertEqual((root / rel).read_text().count(new), 1)

    def test_missing_and_ambiguous(self):
        for s in ("missing", "old old"):
            with self.assertRaises(ValueError):
                m.replace_exact(s, "old", "new")

if __name__ == "__main__":
    unittest.main()
