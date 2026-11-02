"""Archive metadata, spoken text and the bounded online catalogue."""
import hashlib
import html
import json
import re
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from xml.etree import ElementTree as ET

CHINA = timezone(timedelta(hours=8))
ITUNES = 'http://www.itunes.com/dtds/podcast-1.0.dtd'
ATOM = 'http://www.w3.org/2005/Atom'
ET.register_namespace('itunes', ITUNES)
ET.register_namespace('atom', ATOM)


def clean_markdown(text):
    text = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', text)
    text = re.sub(r'!\[[^\]]*\]\[[^\]]*\]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', text)
    text = re.sub(r'^\s*\[[^\]]+\]:.*$', '', text, flags=re.M)
    text = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', '', text, flags=re.S | re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'https?://[^\s<>]+', '', text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r'^\s*(?:#{1,6}\s*|>\s*|[-+*]\s+)', '', line)
        if re.fullmatch(r'\s*(?:[-*_]{3,}|```.*|~~~.*)\s*', line):
            continue
        line = re.sub(r'\\([\\`*_{}\[\]()#+.!|>-])', r'\1', line)
        line = line.replace('**', '').replace('__', '').replace('`', '')
        line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', line)
        lines.append(line.strip())
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def article_id(url):
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if parts.hostname == 'mp.weixin.qq.com' and all(k in query for k in ('__biz', 'mid', 'idx')):
        key = urlencode([(k, query[k][0]) for k in ('__biz', 'mid', 'idx')])
    else:
        key = url.split('#')[0]
    return hashlib.sha256(key.encode()).hexdigest()[:20]


def parse_publish_time(value):
    value=str(value or '').strip()
    if not value:
        return ''
    for fmt in ('%Y年%m月%d日 %H:%M','%Y年%m月%d日 %H:%M:%S'):
        try:
            return datetime.strptime(value,fmt).replace(tzinfo=CHINA).isoformat()
        except ValueError:
            pass
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return (parsed.replace(tzinfo=CHINA) if parsed.tzinfo is None else parsed.astimezone(CHINA)).isoformat()
    except ValueError:
        return ''


def scan_archive(root):
    root = Path(root).expanduser().resolve()
    articles = {}
    for manifest in sorted(root.rglob('style_corpus.jsonl')):
        for number, line in enumerate(manifest.read_text(encoding='utf-8-sig').splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                url = row['url']
                parts = urlsplit(url)
                if parts.scheme != 'https' or parts.hostname != 'mp.weixin.qq.com':
                    raise ValueError('不是微信文章 HTTPS 地址')
                aid = article_id(url)
                if aid in articles:
                    continue
                published = parse_publish_time(row.get('publish_time'))
                source = (manifest.parent / row['markdown_path']).resolve()
                if not source.is_relative_to(manifest.parent.resolve()):
                    raise ValueError('文章路径超出归档目录')
                body = clean_markdown(source.read_text(encoding='utf-8-sig'))
                if not body:
                    raise ValueError('文章正文为空')
                account = manifest.parent.name
                intro = f"{row['title']}。\n\n来源，{account}。"
                if row.get('author') and row['author'] != account:
                    intro += f"作者，{row['author']}。"
                speech = intro + '\n\n' + body
                articles[aid] = dict(id=aid, title=row['title'], account=account,
                                     author=row.get('author', ''), source_url=url,
                                     published_at=published, raw_publish_time=row.get('publish_time') or '', source_path=str(source),
                                     speech=speech,
                                     content_sha256=hashlib.sha256(speech.encode()).hexdigest())
            except (KeyError, ValueError, OSError) as exc:
                raise ValueError(f'{manifest}:{number}: {exc}') from exc
    return sorted(articles.values(), key=lambda a: (a['published_at'], a['id']), reverse=True)


def select_online(current, incoming, limit=20):
    """Explicitly selected incoming articles win over existing articles, regardless of date."""
    selected = {item['id']: item for item in incoming}
    if not selected or len(selected) > limit:
        raise ValueError(f'每次请选择 1–{limit} 篇文章')
    existing = {item['id']: item for item in current if item['id'] not in selected}
    removed = []
    for item in sorted(existing.values(), key=lambda a: (a['published_at'], a['id'])):
        if len(existing) + len(selected) <= limit:
            break
        removed.append(existing.pop(item['id']))
    online = list(existing.values()) + list(selected.values())
    return sorted(online, key=lambda a: (a['published_at'], a['id']), reverse=True), removed


def make_rss(episodes, base_url):
    base_url = base_url.rstrip('/')
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    for name, value in [('title', '微信文章'), ('link', base_url + '/feed.xml'),
                        ('description', '个人收藏的微信文章，使用 macOS 语音朗读。'),
                        ('language', 'zh-cn'), ('ttl', '5')]:
        ET.SubElement(channel, name).text = value
    ET.SubElement(channel, f'{{{ATOM}}}link', href=base_url+'/feed.xml', rel='self', type='application/rss+xml')
    ET.SubElement(channel, f'{{{ITUNES}}}author').text = '微信文章'
    ET.SubElement(channel, f'{{{ITUNES}}}explicit').text = 'false'
    for ep in sorted(episodes, key=lambda a: (a['published_at'], a['id']), reverse=True):
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = ep['account'] + '｜' + ep['title']
        ET.SubElement(item, 'guid', isPermaLink='false').text = 'wechat-' + ep['id']
        ET.SubElement(item, 'link').text = ep['source_url']
        ET.SubElement(item, 'pubDate').text = format_datetime(datetime.fromisoformat(ep['published_at']))
        date_note='\n原文发布日期未知；节目日期使用首次导入时间。' if ep.get('date_source')=='imported' else ''
        ET.SubElement(item, 'description').text = (
            f"来源：{ep['account']}\n作者：{ep['author']}\n原文：{ep['source_url']}\nmacOS TTS 朗读"+date_note)
        ET.SubElement(item, f'{{{ITUNES}}}author').text = ep['author'] or ep['account']
        ET.SubElement(item, f'{{{ITUNES}}}duration').text = str(round(ep['duration']))
        ET.SubElement(item, 'enclosure', url=base_url+'/audio/'+ep['audio_file'],
                      length=str(ep['audio_bytes']), type='audio/mpeg')
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
