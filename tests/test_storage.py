import tempfile
import unittest
from pathlib import Path
from lyfind.storage import resolve_upload
from lyfind.users import DomainError


class StorageTests(unittest.TestCase):
    def test_relative_and_legacy_references_resolve_locally(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'image.png';target.write_bytes(b'test')
            for reference in ['image.png','C:/old/project/image.png',r'C:\old\project\image.png']:
                self.assertEqual(resolve_upload(directory,reference,True),target.resolve())

    def test_traversal_and_missing_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for reference in ['../secret.png',r'..\secret.png','absent.png','']:
                with self.subTest(reference=reference),self.assertRaises(DomainError):resolve_upload(directory,reference,True)
