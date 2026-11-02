import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat2podcast.client import Client


class ClientTests(unittest.TestCase):
    def test_failed_cleanup_does_not_hide_successful_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)/'config.json'
            config.write_text(json.dumps(dict(ssh_host='host', remote_root='/srv/test')))
            client = Client(config)
            def remote(action, request=None):
                if action == 'abort':
                    raise subprocess.CalledProcessError(255, 'ssh')
                return {'episodes': []}
            with patch.object(client, 'remote', side_effect=remote):
                self.assertEqual(client.publish([], [], 'rev'), {'episodes': []})


if __name__ == '__main__':
    unittest.main()
