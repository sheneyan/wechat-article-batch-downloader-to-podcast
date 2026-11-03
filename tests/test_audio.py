import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat2podcast.audio import preview_text, render_audio


class AudioTests(unittest.TestCase):
    def test_preview_stops_at_sentence_boundary(self):
        text = '第一句话。\n\n第二句话！第三句话。'
        self.assertEqual(preview_text(text, 9), '第一句话。')

    def test_failed_speech_preserves_previous_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder/'speech.txt').write_text('文章正文。')
            (folder/'audio.mp3').write_bytes(b'previous')
            with patch('wechat2podcast.audio.subprocess.run', side_effect=RuntimeError('tts failed')):
                with self.assertRaises(RuntimeError):
                    render_audio(folder/'speech.txt', folder/'audio.mp3', 'Tingting', 180)
            self.assertEqual((folder/'audio.mp3').read_bytes(), b'previous')
            self.assertEqual(list(folder.glob('*.aiff')), [])


if __name__ == '__main__':
    unittest.main()
