import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat2podcast.gui import dashboard, handle
from wechat2podcast.settings import load_config, save_config
from wechat2podcast.library import atomic_json


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root/'library'
        self.folder = self.library/('a'*20)
        self.folder.mkdir(parents=True)
        self.article = dict(id='a'*20,title='文章',account='来源',author='作者',
                            published_at='2026-11-01T12:00:00+08:00',source_url='https://mp.weixin.qq.com/s/x',
                            source_path='/archive/article.md',content_sha256='b'*64,speech='正文。')
        atomic_json(self.folder/'article.json', self.article)

    def test_local_readiness_is_separate_from_online_state(self):
        result = dashboard(self.library)
        self.assertEqual(result['articles'][0]['local_state'], 'missing')
        self.assertNotIn('online', result['articles'][0])
        (self.folder/'audio.mp3').write_bytes(b'mp3')
        atomic_json(self.folder/'audio.json', dict(content_sha256='b'*64,preview=False,
                    audio_bytes=3,duration=1,audio_sha256='c'*64))
        result = dashboard(self.library)
        self.assertEqual(result['articles'][0]['local_state'], 'ready')
        self.assertEqual(result['articles'][0]['audio_bytes'], 3)
        self.article['content_sha256'] = 'd'*64
        atomic_json(self.folder/'article.json', self.article)
        self.assertEqual(dashboard(self.library)['articles'][0]['local_state'], 'stale')

    def test_publish_uses_previously_previewed_revision(self):
        req = dict(action='publish', library=str(self.library), config=str(self.root/'config.json'), ids=['a'*20], revision='old')
        with patch('wechat2podcast.gui.Library.publishable', return_value=({}, self.folder/'audio.mp3')):
            with patch('wechat2podcast.gui.Client') as client:
                client.return_value.remote.return_value={'revision':'new','episodes':[]}
                with self.assertRaises(ValueError):
                    handle(req)
                client.return_value.publish.assert_not_called()

    def test_online_network_failure_is_not_an_empty_catalogue(self):
        with patch('wechat2podcast.gui.Client') as client:
            client.return_value.remote.side_effect=OSError('offline')
            with self.assertRaises(OSError):
                handle(dict(action='online', library=str(self.library), config='unused'))

    def test_save_config_derives_paths_and_preserves_ssh_options(self):
        path = self.root/'config.json'
        result = save_config(path, dict(ssh_host='racknerd-4fc9d3f',ssh_user='sheneyan',ssh_port=2222,
                     identity_file='/Users/example/.ssh/my key',remote_root='/srv/wechat2podcast',base_url='https://podcast.example'))
        self.assertEqual(result['remote_code'], '/srv/wechat2podcast/app')
        self.assertTrue(result['base_url'].startswith('https://podcast.example/wechat/'))
        self.assertEqual(result['ssh_port'], 2222)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(load_config(path)['token'], result['token'])

    def test_legacy_config_user_at_host_is_normalized(self):
        path=self.root/'config.json'
        atomic_json(path,dict(ssh_host='sheneyan@racknerd-4fc9d3f',remote_root='/srv/wechat2podcast',
                             base_url='https://podcast.test/wechat/secret',token='secret'))
        cfg=load_config(path)
        self.assertEqual(cfg['ssh_host'], 'racknerd-4fc9d3f')
        self.assertEqual(cfg['ssh_user'], 'sheneyan')

    def test_rejects_ssh_option_and_remote_traversal(self):
        settings=dict(ssh_host='-oProxyCommand=x',ssh_user='user',remote_root='/srv/a',base_url='https://pod.test')
        with self.assertRaises(ValueError):
            save_config(self.root/'config.json',settings)
        settings.update(ssh_host='host',remote_root='/srv/../etc')
        with self.assertRaises(ValueError):
            save_config(self.root/'config.json',settings)


if __name__ == '__main__':
    unittest.main()
