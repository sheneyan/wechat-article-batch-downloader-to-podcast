# 口播稿收件接口 v1

用途：外部 Bot 推送纯文字口播稿，Mac 稍后下载并转音频。它与既有 RSS、音频存储和发布操作独立，不自动 TTS 或上线。给 Bot 写入密钥，Mac 保留另一把读取密钥。

## 写入

`POST <BASE_URL>/v1/scripts`

```http
Authorization: Bearer <WRITE_TOKEN>
Content-Type: application/json; charset=utf-8
```

```json
{
  "id": "daily-x-2026-11-03",
  "title": "每日 X 口播 · 2026-11-03",
  "date": "2026-11-03",
  "text": "今天更值得盯的，是……",
  "notes": "读音备注单独保存，不进入朗读正文。",
  "source_urls": ["https://x.com/example/status/123"]
}
```

必填 `title`（1–200 字符）、`date`（YYYY-MM-DD）、`text`（1–50,000 字符）。可选 `id`（1–100 个字母/数字/点/短横线/下划线），默认 `daily-x-<date>`；可选 `notes`（最多 20,000 字符），`source_urls`（最多 100 个 HTTP(S) 链接）。整个 UTF-8 JSON 请求最多 256 KiB。

首次提交返回 **201**：

```json
{"stored":true,"id":"daily-x-2026-11-03","seq":1,"sha256":"…","created_at":"…+00:00","bytes":1234,"duplicate":false}
```

相同 ID、相同规范化内容重试返回 **200**，`duplicate:true`，仍是同一条。相同 ID、不同内容返回 **409**，不会覆盖原文；需要修订时显式使用 `daily-x-2026-11-03-v2`。SHA256 对排序键、紧凑 UTF-8 JSON 的规范化文档计算，不包含回执时间等服务端字段。

## 查验回执

`GET <BASE_URL>/v1/receipts/<id>`，使用同一写入密钥。返回 ID、SHA256、序号、接收时间和大小，不返回正文。Bot 应报告真实 HTTP 状态与回执，不能把生成的 curl 命令当作上传成功。

## Mac 读取

- `GET <BASE_URL>/v1/scripts?after=0&limit=50`：使用 **READ_TOKEN**；按序号递增分页。返回 `items` 元数据、`next_cursor` 和 `has_more`，不含正文。limit 为 1–100。
- `GET <BASE_URL>/v1/scripts/<id>`：使用 **READ_TOKEN**；返回正文、备注、来源和回执信息。
- 写入密钥不能读正文，读取密钥不能新增稿件。URL 查询参数不接受密钥认证。
- `GET <BASE_URL>/healthz`：不需认证，仅返回服务健康信息，不暴露稿件。

本地读取配置：

```json
{"base_url":"https://example.com/brief-inbox","read_token":"<READ_TOKEN>"}
```

```sh
python3 -m wechat2podcast.inbox_client --config /private/inbox-reader.json
```

默认保存到 `.local/grok-inbox/`：JSON 保留完整字段，`.txt` 仅包含朗读正文，`.notes.txt` 仅包含备注。验证 SHA256 后再推进本地游标；重复拉取不重复创建条目。`--from-start` 可重新拉取。此工具暂不接入 App 音频列表，也不自动转换/发布。

## 错误和运行边界

| 状态 | 含义 |
| --- | --- |
| 400 | JSON、必填字段、日期、ID 或参数无效 |
| 401 | 无密钥、错误密钥或使用了错误角色的密钥 |
| 404 | 路径或稿件不存在 |
| 408 | 请求读取超时 |
| 409 | 同编号存在不同内容 |
| 413 | 请求超过 256 KiB |
| 415 | 不是 application/json |
| 503 | 存储暂时不可用，可退避重试 |
| 507 | 收稿数量/文字容量达到上限 |

服务使用 SQLite 事务保存，回执在提交完成后返回。上限 10,000 稿件、128 MiB 规范化文档文本；这与最多在线 20 篇音频是两个独立规则。稿件原文保存在私有目录，不放入 nginx 静态目录，没有远程删除或执行命令接口。

## 部署

现有 SSH 发布配置和已配置 HTTPS/nginx 的服务器可运行：

```sh
PYTHONPATH=. python3 script/deploy_inbox.py --nginx-site /etc/nginx/sites-available/your-existing-site
```

要求 SSH 用户具备非交互 sudo、站点包含既有 wechat2podcast nginx include。服务名 `wechat2podcast-inbox`，监听 `127.0.0.1:18769`，nginx `/brief-inbox/` 转发至本机服务；不改变 `/wechat/` 或原播客中转。系统服务使用非 root 用户与独立私有数据目录。

配置和生成的读写密钥位于 `.private/`，不进入 Git。重复部署沿用已有密钥；本地/远程配置不一致时拒绝隐式轮换。需要停用时 `sudo systemctl stop wechat2podcast-inbox`，删除 nginx include 并检查语法后 reload；数据保留。
