# Job Application Tracker MCP — MVP

> 最后更新：2026-10-24　|　当前进度：3/7，下一步：推到 GitHub、部署到 Render

## 一句话定义

自动读取 linkexin002@gmail.com 的求职邮件，把申请进展记录到 Neon 数据库；在电脑和手机上都能直接问 Claude 查看。

## 技术栈

| 部分 | 选择 |
|---|---|
| 数据库 | Neon (Postgres) |
| MCP Server | Python + FastMCP（HTTP 传输，token 鉴权） |
| 部署 | Render（连接 GitHub，push 后自动部署） |
| 代码托管 | GitHub |
| 邮件来源 | Gmail：linkexin002@gmail.com |

## MVP 范围（6 件事）

| # | 功能 | 说明 |
|---|---|---|
| 1 | Neon 数据表 `applications` + `status_events` | company, role, status, deadline, next_step, city, link, notes, source, source_email, updated_at；`status_events` 记录每次状态变化和证据 |
| 2 | MCP Server | 4 个工具：`add_application`、`update_status`、`list_upcoming`、`list_applications` |
| 3 | 每日 Gmail 自动同步 | Claude 定时任务每天读新邮件，识别为 Applied / OA / Interview / Rejected / Offer，再调用 MCP 写入 |
| 4 | 防误判 | 每次自动修改记录来源邮件；没把握的标为“待确认”，不直接改状态；手动修改优先 |
| 5 | 手机查看 | 在 Claude 手机 App 里直接问，比如“这周有什么要截止” |
| 6 | 导入现有表格 | 一次性导入已有记录，之后以 Neon 为准；Gmail 同步时去重 |

**状态流转：** Wishlist → Applied → OA_Pending → OA → Interview → Offer / Rejected

| 原表写法 | 入库状态 |
|---|---|
| 未投递 | Wishlist |
| 空白 | Applied |
| 待测评 / 没做测评 | OA_Pending |
| 完成测评 | OA |
| AI面试 / 专业面试 | Interview |
| 挂 | Rejected |

## 邮件识别要点

识别由 Claude 完成，中英文邮件都能读懂，不依赖固定关键词。

**英文岗位**
- 投递确认：LinkedIn “Your application was sent to…”、Greenhouse、Lever、Workday、Ashby
- 测评：HackerRank、CodeSignal、“online assessment”
- 面试：“schedule an interview”、日程链接
- 拒信：“unfortunately”“move forward with other candidates”

**中文岗位**
- 投递确认：“投递成功”“简历已收到”“感谢您投递”；常见招聘系统如 Moka、北森、飞书招聘
- 测评/笔试：“笔试邀请”“在线测评”“性格测评”；牛客、赛码、北森测评
- 面试：“面试邀请”“一面”“二面”“HR 面”，含时间和会议链接
- 拒信：“很遗憾”“未能进入下一轮”“已进入人才库”“感谢您的关注”
- Offer：“录用通知”“意向书”“offer”

**注意**
- offer、interview、面试这类词会搜到大量营销和求职机构邮件，要结合发件人和内容判断
- 很多中文公司用短信、公众号或招聘 App 通知，Gmail 看不到，这部分需要手动补一句话更新
- 一封邮件里同时出现公司名的中英文（如“字节跳动 / ByteDance”），入库时统一成一个公司名，避免重复

## 不做（放到 v2）

- Excel 导出、`/dashboard` 网页
- 面试前公司调研 Skill
- 服务器端直接调用 Gmail API
- Handshake、Canvas、日历同步

## 完成标准

1. 新投一个岗位，第二天数据库里自动出现这条记录，状态是 Applied
2. 收到测评或拒信后状态自动更新，并且能查到是哪封邮件触发的
3. 在手机上问 Claude，能得到正确的即将截止列表

## 进度

- [x] 1. Neon 建库建表（`schema.sql`：`applications` + `status_events`）— 2026-10-23 完成
- [x] 2. 导入现有表格：180 条（Applied 115 / Wishlist 27 / Rejected 15 / OA 13 / Interview 5 / OA_Pending 5），已在 Neon 控制台核对 — 2026-10-23 完成
- [x] 3. 本地写 `db.py` 和 4 个 MCP 工具，冒烟测试 7 项全部通过 — 2026-10-24 完成
- [ ] 4. 推到 GitHub，在 Render 部署，配置环境变量（数据库连接串、token）
- [ ] 5. 在 Claude 电脑端和手机端接入 MCP 连接器
- [ ] 6. 设置每日 Gmail 同步定时任务
- [ ] 7. 按完成标准做端到端测试

## 安全

- 数据库连接串和 token 只放在 Render 环境变量和本地 `.env` 里，`.env` 加进 `.gitignore`，不提交到 GitHub
- MCP 部署到公网后必须开启 token 鉴权
- Render 和 Neon 的免费套餐闲置后会休眠，首次请求可能要等几十秒

## 决策记录

- 2026-10-24：`data/`（含个人投递记录）不上传 GitHub，只留在本地

- 2026-10-23：MCP 用 Python SDK 1.x（`mcp<2`）；鉴权用 MCP_TOKEN，支持 Bearer 头或 `?key=` 参数

- 2026-10-23：沙盒网络连不上 Neon，数据库相关脚本在本机终端运行

- 2026-10-23：新增状态 Wishlist、OA_Pending；原表第 107–132 行错位段整理后默认记为 Wishlist

- 2026-10-22：放弃合并 Handshake、Canvas、Google Calendar，聚焦求职申请追踪
- 2026-10-23：支持中英文求职邮件识别
- 2026-10-23：数据存 Neon，部署用 Render，代码放 GitHub；状态更新由 Gmail 自动识别；手机端通过 Claude 查看
