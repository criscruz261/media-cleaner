import tempfile
import unittest
from pathlib import Path

from app import delete_selected, file_identity, scan_folder


class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in ['a.jpg', 'b.jpg']:
            (self.root / name).write_bytes(b'photo')
        self.result, self.files = scan_folder(self.root)
        self.ids = [file['id'] for file in self.result['groups'][0]['files']]
        self.identities = {token: file_identity(path) for token, path in self.files.items()}

    def delete(self, ids):
        return delete_selected(self.result, self.files, self.identities, ids)

    def test_only_requested_copy_deleted(self):
        outcome = self.delete(self.ids[:1])
        self.assertEqual(len(outcome['deleted']), 1)
        self.assertEqual(outcome['errors'], [])
        self.assertTrue(self.files[self.ids[1]].exists())
        self.assertFalse(self.files[self.ids[0]].exists())

    def test_all_copies_or_unknown_ids_rejected(self):
        for ids in [self.ids, ['unknown'], [], [self.ids[0], self.ids[0]]]:
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.delete(ids)
        self.assertTrue(all(path.exists() for path in self.files.values()))

    def test_changed_file_blocks_deletion(self):
        self.files[self.ids[0]].write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.delete(self.ids[:1])
        self.assertTrue(all(path.exists() for path in self.files.values()))

    def test_missing_keeper_blocks_deletion(self):
        self.files[self.ids[1]].unlink()
        with self.assertRaises(OSError):
            self.delete(self.ids[:1])
        self.assertTrue(self.files[self.ids[0]].exists())

    def test_symlink_replacement_blocks_deletion(self):
        path = self.files[self.ids[0]]
        path.unlink()
        path.symlink_to(self.files[self.ids[1]])
        with self.assertRaises(ValueError):
            self.delete(self.ids[:1])
        self.assertTrue(self.files[self.ids[1]].exists())


class GroupDeleteTests(unittest.TestCase):
    def test_group_deletion_preserves_other_group_and_requires_fresh_confirmation(self):
        import io
        import json
        import threading
        from email.message import Message
        from types import SimpleNamespace
        from unittest.mock import Mock
        from app import Handler

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for name, content in [('a.jpg', b'first'), ('b.jpg', b'first'), ('c.jpg', b'second'), ('d.jpg', b'second')]:
                (root / name).write_bytes(content)
            result, files = scan_folder(root)
            result['delete_token'] = 'initial-token'
            server = SimpleNamespace(lock=threading.Lock(), server_port=8765,
                                     state={'status': 'done', 'result': result}, files=files,
                                     identities={token: file_identity(path) for token, path in files.items()})
            first, second = result['groups']

            def request(ids, token, confirmed=True):
                payload = json.dumps({'ids': ids, 'delete_token': token, 'confirmed': confirmed}).encode()
                handler = Handler.__new__(Handler)
                handler.path = '/api/delete'
                handler.server = server
                handler.headers = Message()
                handler.headers['Host'] = '127.0.0.1:8765'
                handler.headers['Content-Length'] = str(len(payload))
                handler.rfile = io.BytesIO(payload)
                handler.reply = Mock()
                handler.do_POST()
                return handler.reply.call_args.args

            ids = [first['files'][0]['id']]
            self.assertEqual(request(ids, 'initial-token', False)[0], 400)
            code, outcome = request(ids, 'initial-token')
            self.assertEqual(code, 200)
            self.assertEqual(len(outcome['deleted']), 1)
            self.assertEqual(server.state['result']['groups'], [second])
            self.assertTrue(all(Path(file['path']).exists() for file in second['files']))
            self.assertEqual(request([second['files'][0]['id']], 'initial-token')[0], 400)
            token = server.state['result']['delete_token']
            self.assertEqual(request([second['files'][0]['id']], token)[0], 200)
            self.assertEqual(server.state['result']['groups'], [])
