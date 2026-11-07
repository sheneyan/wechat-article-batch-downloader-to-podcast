import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

spec=importlib.util.spec_from_file_location('setup_qwen',Path(__file__).parents[1]/'script/setup_qwen.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_corrupt_equal_length_cached_part_is_cleared_and_retry_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);part=root/'model.safetensors.0.part';part.write_bytes(b'bad')
            manifest=dict(Code=200,Data=dict(Files=[dict(Type='blob',Path='model.safetensors',Size=3,Sha256=hashlib.sha256(b'yes').hexdigest())]))
            opener=Mock();opener.open.side_effect=lambda *a,**k:io.BytesIO(json.dumps(manifest).encode())
            with patch.object(setup.urllib.request,'build_opener',return_value=opener):
                with self.assertRaisesRegex(ValueError,'SHA256'):setup.download_model(root)
                self.assertFalse(part.exists())
                self.assertFalse((root/'model.safetensors.download').exists())
                def curl(args,**kwargs):Path(args[-1]).write_bytes(b'yes')
                with patch.object(setup.subprocess,'run',side_effect=curl):setup.download_model(root)
                self.assertEqual((root/'model.safetensors').read_bytes(),b'yes')
                self.assertTrue(all('Revision=master' not in str(call) for call in opener.open.call_args_list))
