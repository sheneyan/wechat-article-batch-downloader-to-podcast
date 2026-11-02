import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from wechat2podcast.core import clean_markdown, scan_archive, select_online, make_rss


def episode(n, date=None):
    return dict(id=f'{n:020x}', title=f'文章 & {n}', account='公众号', author='作者',
                source_url='https://mp.weixin.qq.com/s?a=1&b=2',
                published_at=date or f'2026-10-{n:02d}T12:00:00+08:00',
                audio_file=f'{n:064x}.mp3', audio_sha256=f'{n:064x}', audio_bytes=100, duration=62)


class CoreTests(unittest.TestCase):
    def test_cleanup_preserves_paragraphs_and_link_text(self):
        self.assertEqual(clean_markdown('# 标题\n\n![图](images/a.png)\n\n**正文**与[链接](https://a.test/x)。\n\n&gt; 引用'),
                         '标题\n\n正文与链接。\n\n引用')

    def test_scans_accounts_deduplicates_url_and_retains_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for account in ['A甲', 'B乙']:
                p = root/account
                (p/'markdown').mkdir(parents=True)
                (p/'markdown/a.md').write_text('第一段。\n\n第二段。')
                rows = [dict(title='文章', author='作者', url='https://mp.weixin.qq.com/s?mid=1&__biz=x&idx=1&scene=2',
                             publish_time='2026年10月02日 00:29', markdown_path='markdown/a.md')]
                if account == 'B乙':
                    rows.append({**rows[0], 'url':'https://mp.weixin.qq.com/s?__biz=y&mid=2&idx=1'})
                (p/'style_corpus.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
            result = scan_archive(root)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['published_at'], '2026-10-02T00:29:00+08:00')
            self.assertEqual({r['account'] for r in result}, {'A甲', 'B乙'})

    def test_new_upload_evicts_oldest_existing_even_if_new_is_older(self):
        current = [episode(n) for n in range(1, 21)]
        incoming = episode(21, '2020-01-01T00:00:00+08:00')
        online, removed = select_online(current, [incoming])
        self.assertEqual(len(online), 20)
        self.assertEqual([r['id'] for r in removed], [episode(1)['id']])
        self.assertIn(incoming, online)

    def test_republish_does_not_duplicate_or_evict(self):
        current = [episode(n) for n in range(1, 21)]
        online, removed = select_online(current, [episode(2)])
        self.assertEqual(len(online), 20)
        self.assertEqual(removed, [])

    def test_more_than_twenty_selected_rejected(self):
        with self.assertRaises(ValueError):
            select_online([], [episode(n) for n in range(1, 22)])

    def test_rss_has_single_channel_stable_guid_and_escaped_metadata(self):
        xml = make_rss([episode(1)], 'https://podcast.test/wechat/private')
        root = ET.fromstring(xml)
        self.assertEqual(root.findtext('channel/title'), '微信文章')
        item = root.find('channel/item')
        self.assertEqual(item.findtext('title'), '公众号｜文章 & 1')
        self.assertEqual(item.findtext('guid'), 'wechat-00000000000000000001')
        self.assertEqual(item.find('enclosure').get('type'), 'audio/mpeg')
        self.assertEqual(item.find('enclosure').get('length'), '100')
        self.assertIn('/audio/', item.find('enclosure').get('url'))


if __name__ == '__main__':
    unittest.main()
