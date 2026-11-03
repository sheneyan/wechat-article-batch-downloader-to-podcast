import tempfile
import unittest
from pathlib import Path
from wechat2podcast import inbox_settings


class InboxSettingsTests(unittest.TestCase):
    def test_private_profile_roundtrip_and_host_change_requires_new_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'inbox-reader.json'
            self.assertEqual(inbox_settings.load(path)['read_token'],'')
            cfg=dict(base_url='https://pod.test/brief-inbox/',read_token='a'*64)
            result=inbox_settings.save(path,cfg)
            self.assertEqual(result['base_url'],'https://pod.test/brief-inbox')
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):
                inbox_settings.save(path,{**cfg,'base_url':'https://other.test/brief-inbox'})
            self.assertEqual(inbox_settings.load(path),result)

    def test_missing_profile_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'读取密钥'):
                inbox_settings.required(Path(tmp)/'missing.json')


if __name__=='__main__':
    unittest.main()
