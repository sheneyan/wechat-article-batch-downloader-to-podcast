import hashlib
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
from unittest.mock import patch
import os

from test_core import episode
from wechat2podcast.remote import Publisher


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pub = Publisher(self.root, 'https://test/wechat/secret', 'secret')

    def stage(self, n, payload=None, batch='a'*32):
        payload = payload or f'audio{n}'.encode()
        ep = episode(n)
        sha = hashlib.sha256(payload).hexdigest()
        ep.update(audio_file=sha+'.mp3', audio_sha256=sha, audio_bytes=len(payload))
        folder = self.root / '.staging' / batch
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ep['audio_file']).write_bytes(payload)
        return ep

    def test_first_publish_and_republish(self):
        ep = self.stage(1)
        status = self.pub.commit([ep], 'a'*32, self.pub.status()['revision'])
        self.assertEqual(len(status['episodes']), 1)
        self.assertTrue((self.pub.public / 'audio' / ep['audio_file']).exists())
        self.pub.commit([ep], 'b'*32, status['revision'])
        self.assertEqual(len(self.pub.status()['episodes']), 1)

    def test_missing_audio_never_changes_feed(self):
        self.pub.commit([self.stage(1)], 'a'*32, self.pub.status()['revision'])
        before = (self.pub.public/'feed.xml').read_bytes()
        with self.assertRaises(ValueError):
            self.pub.commit([episode(2)], 'c'*32, self.pub.status()['revision'])
        self.assertEqual((self.pub.public/'feed.xml').read_bytes(), before)

    def test_hash_mismatch_never_publishes(self):
        ep = self.stage(1)
        (self.root/'.staging'/('a'*32)/ep['audio_file']).write_bytes(b'corrupted')
        with self.assertRaises(ValueError):
            self.pub.commit([ep], 'a'*32, self.pub.status()['revision'])
        self.assertEqual(self.pub.status()['episodes'], [])

    def test_conflicting_publication_rejected(self):
        revision = self.pub.status()['revision']
        self.pub.commit([self.stage(1)], 'a'*32, revision)
        with self.assertRaises(ValueError):
            self.pub.commit([self.stage(2, batch='b'*32)], 'b'*32, revision)
        self.assertEqual(len(self.pub.status()['episodes']), 1)

    def test_twenty_first_removes_old_audio_and_keeps_new(self):
        eps = [self.stage(n) for n in range(1,21)]
        self.pub.commit(eps, 'a'*32, self.pub.status()['revision'])
        ep = self.stage(21, batch='b'*32)
        result = self.pub.commit([ep], 'b'*32, self.pub.status()['revision'])
        self.assertEqual(len(result['episodes']), 20)
        self.assertFalse((self.pub.public/'audio'/eps[0]['audio_file']).exists())
        self.assertEqual(len(list((self.pub.public/'audio').glob('*.mp3'))), 20)
        self.assertEqual(len(ET.parse(self.pub.public/'feed.xml').findall('channel/item')),20)

    def test_invalid_filename_rejected(self):
        ep = self.stage(1)
        ep['audio_file'] = '../../secret'
        with self.assertRaises(ValueError):
            self.pub.commit([ep], 'a'*32, self.pub.status()['revision'])

    def test_pointer_failure_keeps_old_feed_and_cleans_new_audio(self):
        self.pub.commit([self.stage(1)], 'a'*32, self.pub.status()['revision'])
        before = (self.pub.public/'feed.xml').read_bytes()
        new = self.stage(2, batch='b'*32)
        replace = os.replace

        def fail_pointer(source, destination):
            if Path(destination) == self.root/'current':
                raise OSError('simulated pointer failure')
            return replace(source, destination)

        with patch('wechat2podcast.remote.os.replace', side_effect=fail_pointer):
            with self.assertRaises(OSError):
                self.pub.commit([new], 'b'*32, self.pub.status()['revision'])
        self.assertEqual((self.pub.public/'feed.xml').read_bytes(), before)
        self.assertFalse((self.pub.public/'audio'/new['audio_file']).exists())

    def test_invalid_xml_metadata_cannot_replace_live_feed(self):
        ep = self.stage(1)
        ep['title'] = 'bad\x01title'
        with self.assertRaises(ValueError):
            self.pub.commit([ep], 'a'*32, self.pub.status()['revision'])
        self.assertEqual(self.pub.status()['episodes'], [])

    def test_cleanup_failure_reports_committed_catalogue_and_can_retry(self):
        eps = [self.stage(n) for n in range(1, 21)]
        self.pub.commit(eps, 'a'*32, self.pub.status()['revision'])
        new = self.stage(21, batch='b'*32)
        unlink = Path.unlink

        def fail_old(path, *args, **kwargs):
            if path == self.pub.public/'audio'/eps[0]['audio_file']:
                raise PermissionError('simulated cleanup failure')
            return unlink(path, *args, **kwargs)

        with patch.object(Path, 'unlink', fail_old):
            result = self.pub.commit([new], 'b'*32, self.pub.status()['revision'])
        self.assertEqual(len(result['episodes']), 20)
        self.assertTrue(result['warnings'])
        self.assertEqual(result['revision'], self.pub.status()['revision'])
        self.pub.commit([new], 'c'*32, result['revision'])
        self.assertEqual(len(list((self.pub.public/'audio').glob('*.mp3'))), 20)

    def test_unpublish_last_episode_keeps_valid_empty_feed(self):
        ep=self.stage(1)
        state=self.pub.commit([ep], 'a'*32, self.pub.status()['revision'])
        result=self.pub.remove([ep['id']],state['revision'])
        self.assertEqual(result['episodes'], [])
        self.assertEqual(len(ET.parse(self.pub.public/'feed.xml').findall('channel/item')),0)
        self.assertFalse((self.pub.public/'audio'/ep['audio_file']).exists())

    def test_populated_root_rejects_different_program_token(self):
        self.pub.commit([self.stage(1)], 'a'*32, self.pub.status()['revision'])
        with self.assertRaises(ValueError):
            Publisher(self.root,'https://test/wechat/different','different')

    def test_publisher_created_before_other_program_cannot_rebind_root(self):
        other=Publisher(self.root,'https://test/wechat/different','different')
        self.pub.commit([self.stage(1)],'a'*32,self.pub.status()['revision'])
        revision=self.pub.status()['revision']
        ep=self.stage(1,batch='b'*32)
        with self.assertRaisesRegex(ValueError,'节目标识'):
            other.commit([ep],'b'*32,revision)
        self.assertEqual(self.pub.status()['revision'],revision)

    def test_deployment_rejects_token_change_without_overwriting_profile(self):
        from wechat2podcast.remote import configure
        import json
        config=self.root/'config.json'
        original=dict(root=str(self.root),base_url='https://test/wechat/secret',token='secret')
        configure(config,original)
        self.pub.commit([self.stage(1)],'a'*32,self.pub.status()['revision'])
        with self.assertRaises(ValueError):
            configure(config,{**original,'token':'different','base_url':'https://test/wechat/different'})
        self.assertEqual(json.loads(config.read_text()),original)


if __name__ == '__main__':
    unittest.main()
