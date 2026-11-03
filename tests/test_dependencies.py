import unittest
from unittest.mock import patch
from wechat2podcast.dependencies import check_dependencies, require_audio


class DependencyTests(unittest.TestCase):
    def test_missing_encoder_is_reported_before_speech(self):
        with patch('wechat2podcast.dependencies.shutil.which',side_effect=lambda name: None if name=='ffmpeg' else '/usr/bin/'+name):
            with patch('wechat2podcast.dependencies.subprocess.run') as run:
                run.return_value.stdout='Tingting            zh_CN    # voice'
                result=check_dependencies()
                self.assertFalse(result['available'])
                self.assertIn('ffmpeg',result['missing'])
                with self.assertRaises(ValueError):
                    require_audio()

    def test_tailscale_is_optional_for_public_ssh(self):
        with patch('wechat2podcast.dependencies.shutil.which',side_effect=lambda name: None if name=='tailscale' else '/usr/bin/'+name):
            with patch('wechat2podcast.dependencies.subprocess.run') as run:
                run.return_value.stdout='Tingting            zh_CN    # voice'
                self.assertTrue(check_dependencies()['available'])


if __name__ == '__main__':
    unittest.main()
