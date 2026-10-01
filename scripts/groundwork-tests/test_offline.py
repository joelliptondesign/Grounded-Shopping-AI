import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('offline',Path(__file__).resolve().parents[1]/'verify-offline.py')
offline=importlib.util.module_from_spec(spec);spec.loader.exec_module(offline)

class OfflineTests(unittest.TestCase):
    def test_any_failure_is_nonzero_including_known_baseline(self):
        self.assertEqual(offline.result_code({'unit':0,'eval':1}),1)
        self.assertEqual(offline.result_code({'unit':1,'eval':0}),1)
        self.assertEqual(offline.result_code({'unit':0,'eval':0}),0)

    def test_snapshot_uses_working_files_and_excludes_secrets_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';root.mkdir();target=Path(tmp)/'snapshot';target.mkdir()
            subprocess.run(['git','init','-q'],cwd=root,check=True)
            for name,body in [('source.py','old'),('.env','fake secret'),('.env.example','template'),('artifacts/past.md','past'),('.gitignore','ignored/\n')]:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
            subprocess.run(['git','add','.'],cwd=root,check=True)
            (root/'source.py').write_text('working revision')
            (root/'new.py').write_text('untracked revision')
            (root/'ignored').mkdir();(root/'ignored/cache').write_text('skip')
            hashes=offline.source_snapshot(root,target)
            self.assertEqual((target/'source.py').read_text(),'working revision')
            self.assertIn('new.py',hashes)
            for name in ['.env','.env.example','artifacts/past.md','ignored/cache']:
                self.assertFalse((target/name).exists())
            self.assertEqual((root/'artifacts/past.md').read_text(),'past')
            (root/'link.py').symlink_to(root/'source.py')
            with self.assertRaisesRegex(ValueError,'symlink'):
                offline.source_snapshot(root,target)

if __name__=='__main__':unittest.main()
