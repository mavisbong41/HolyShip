# HolyShip 系统实现文档（Batch 1 + Batch 2 当前进展）

> 业务目标：生产级航运单证核验系统（Shipping Document Verification System）
> 当前阶段：Batch 1 邮件接入分类已完成 + Batch 2 文档理解与解析基础已就绪

---

## 目录
- [一、Batch 1 已完成内容（邮件接入与双阶段分类引擎）](#一batch-1-已完成内容邮件接入与双阶段分类引擎)
  - [1. 基础架构（Source-Independent Ingestion）](#1-基础架构source-independent-ingestion)
  - [2. 数据库设计（PostgreSQL + SQLAlchemy 2.x + Alembic）](#2-数据库设计postgresql--sqlalchemy-2x--alembic)
  - [3. 双阶段邮件分类引擎（Two-Stage Classifier）](#3-双阶段邮件分类引擎two-stage-classifier)
  - [4. 初始同步服务（Sync Service）](#4-初始同步服务sync-service)
  - [5. Batch 1 REST APIs](#5-batch-1-rest-apis)
  - [6. 主办方 520 封邮件实测结果](#6-主办方-520-封邮件实测结果)
- [二、Batch 2 已完成内容（文档理解与解析基础）](#二batch-2-已完成内容文档理解与解析基础)
  - [1. 数据库扩展表（Alembic Migration 0002）](#1-数据库扩展表alembic-migration-0002)
  - [2. 统一文档表示（UnifiedDocument Model）](#2-统一文档表示unifieddocument-model)
  - [3. 多层文档读取器（Native First -> OCR -> Vision Fallback）](#3-多层文档读取器native-first---ocr---vision-fallback)
  - [4. 文档路由器（Document Router）](#4-文档路由器document-router)
- [三、自动化测试执行状态](#三自动化测试执行状态)
- [四、Batch 2 下一步任务](#四batch-2-下一步任务)

---

## 一、Batch 1 已完成内容（邮件接入与双阶段分类引擎）

### 1. 基础架构（Source-Independent Ingestion）
系统设计了统一的邮件源抽象层，实现业务分类逻辑与邮件来源完全解耦：
- **`StaticBundleSource`**：读取本地比赛离线文件夹 (`sdoc-hackathon-bundle`)。
- **`OrganizerHttpSource`**：对接主办方 Docker 容器 HTTP API (`/emails`, `/emails/{id}`)。
- **`IncomingApiSource`**：接收实时推送的邮件请求 (`POST /api/email/incoming`)。
- **扩展性**：未来扩展对接真实业务的 `MicrosoftGraphSource`（Outlook/Exchange）无需修改分类引擎一行代码。
- **标准化数据模型**：所有来源无论字段结构如何，均清洗并映射为系统统一的 `EmailMessage`，包含计算好的 `content_hash`，天然支持跨源去重与幂等处理。

### 2. 数据库设计（PostgreSQL + SQLAlchemy 2.x + Alembic）
采用纯 PostgreSQL 方案，已完成第一批表的构建与迁移：
- **`email_messages`**：存储标准化邮件信息、收件人列表 (JSONB)、元数据与内容哈希值 (`content_hash`)。
- **`attachments`**：记录附件基础元数据（文件名、扩展名、MIME 类型、存储引用），**严格不解析附件内容**用于分类。
- **`processing_jobs`**：每封邮件的状态机流水记录（`PENDING` → `INGESTED` → `CLASSIFYING` → `CLASSIFIED` / `HUMAN_REVIEW_REQUIRED` / `FAILED`）。
- **`classification_results`**：持久化分类结果，包括最终类别、置信度、各候选类别得分、决策判定原因、证据摘要与裁决阶段。
- **`human_review_cases`**：记录所有进入人工复核的案例、原因码及候选打分证据。

### 3. 双阶段邮件分类引擎（Two-Stage Classifier）
严格遵循集中式决策矩阵与置信度门禁，不使用杂乱的 if/else 堆叠：

- **6 大分类目标**：
  1. `DOCUMENT_COMPARISON`（核心单据比对）
  2. `NEW_SI_REQUEST`（提交/制作新 Shipping Instruction）
  3. `INVOICE_QUERY`（账单与发票查询）
  4. `GENERAL_MAIL`（日常操作通知与 FYI）
  5. `SPAM`（垃圾营销与钓鱼邮件）
  6. `UNCERTAIN`（不确定兜底类别，触发人工复核）

- **信号证据加权体系**：
  - **Body（正文）**：权重 **1.0×**（最高意图依据）
  - **Subject（主题）**：权重 **0.7×**（辅助参考，防止标题党误导）
  - **Attachment Filename（附件名）**：权重 **0.3×**（微弱补充，**附件存在与否绝不单独决定分类**）

- **Stage 1（快速打分门禁）**：
  - 判定条件：`置信度 ≥ 0.80` 且 `Top1 与 Top2 分差 ≥ 0.25` 且 `无冲突` 且 `Body 具有有效支撑信号`。
  - 满足上述条件直接定类，快速完结简单清晰邮件。

- **Stage 2（冲突深度解算）**：
  - 触发情况：Subject 与 Body 矛盾、混合多重意图、候选得分咬合过近、Body 缺乏明确动作词。
  - 解算策略：执行 Body 主导的加权二次计算（Body 1.5×, Subject 0.5×）。
  - 若 `置信度 ≥ 0.65` 且 `分差 ≥ 0.15`，则在 Stage 2 完成定类；仍不明确者安全降级为 `UNCERTAIN` 并自动建立人工复核单。

### 4. 初始同步服务（Sync Service）
- 支持一键拉取主办方全部邮件并入库持久化。
- **绝对幂等性**：重复执行同步时，`content_hash` 未发生变化的邮件自动跳过分类重算；邮件内容变更时自动触发重分类。
- **容错隔离**：单封损坏邮件记录为 `FAILED` 并保留异常堆栈，绝不中断整批同步任务。

### 5. Batch 1 REST APIs
提供标准 FastAPI 接口：
- `GET /api/health`：健康检查。
- `POST /api/sync`：触发批量同步与分类（支持 static 与 http 模式）。
- `GET /api/emails`：分页获取已摄取邮件列表。
- `GET /api/emails/{id}`：获取单封邮件及附件清单。
- `GET /api/emails/{id}/classification`：获取指定邮件的分类结果详情。
- `GET /api/human-review`：查询人工复核案例列表。
- `GET /api/human-review/{id}`：获取单个人工复核详情。
- `POST /api/email/incoming`：接收外部推送新邮件，走完全相同的分类流水线。

### 6. 主办方 520 封邮件实测结果
跑完全部 520 封邮件，无任何异常崩溃，分类分布极其贴合真实业务场景：

| 邮件类别 | 数量 | 占比 | 说明 |
|---|---|---|---|
| `DOCUMENT_COMPARISON` | 214 | 41.2% | 核心单据比对主力任务 |
| `NEW_SI_REQUEST` | 136 | 26.2% | 新提交/制作 SI 单据 |
| `INVOICE_QUERY` | 83 | 16.0% | 账单与费用查询 |
| `GENERAL_MAIL` | 40 | 7.7% | 日常通知与参考 |
| `SPAM` | 26 | 5.0% | 垃圾与钓鱼邮件 |
| `UNCERTAIN` | 21 | 4.0% | 进入人工复核队列 |

- **决策阶段裁决率**：
  - Stage 1 快速直接定类：**52.7%**
  - Stage 2 深度解算定类：**43.3%**
  - 流入人工复核（Human Review）：仅 **4.0%**

---

## 二、Batch 2 已完成内容（文档理解与解析基础）

### 1. 数据库扩展表（Alembic Migration 0002）
已完成迁移脚本 `20260919_0002_create_batch2_document_tables.py`，新增三张关键实体表：
- **`documents`**：记录附件归属的业务角色（`SI` / `DRAFT_BL` / `OTHER` / `UNKNOWN`）与格式（`PLAIN_TEXT` / `PDF_TEXT` / `DOCX` / `XLSX` / `SCANNED_PDF` 等）。
- **`document_extractions`**：记录提取状态、执行的 Reader、文本全文、解析质量与页数。
- **`extracted_fields`**：存储提取出的核心字段（保留原始抽取文本，不提前做归一化）。
- **`human_review_cases` 扩展**：增加了 `document_id` 和 `field_name` 外键/字段。

### 2. 统一文档表示（UnifiedDocument Model）
彻底杜绝为每个格式写一套提取逻辑的坏设计，统一将任何格式转换为通用结构：
- 全文字符串 (`raw_text`)
- 分页对象清单 (`pages`: 包含页码与单页文本)
- 表格对象清单 (`tables`: 包含结构化行和单元格)
- 提取质量、状态与 Reader 元数据

### 3. 多层文档读取器（Native First -> OCR -> Vision Fallback）
- **`PlainTextReader`**：原生解析 `.txt` / `.csv`。
- **`PdfTextReader`**：基于 `pypdf` 优先提取原生矢量文本，自动甄别是否为扫描图或损坏流。
- **`DocxReader`**：基于 `python-docx` 解析段落与 Word 表格数据。
- **`XlsxReader`**：基于 `openpyxl` 解析工作表行列。
- **`OcrReader`**：针对图片与扫描件提取，当本地未装 Tesseract 时优雅报错并记录状态，安全降级而不崩溃。
- **`VisionReader`**：抽象出 `VisionResolver` 接口，预留未来接入大模型 Vision 的插槽。
- **`CompositeDocumentReader`**：编排上述读取链路，自动判断格式并按降级顺序读取。

### 4. 文档路由器（Document Router）
针对 `DOCUMENT_COMPARISON` 邮件附件执行多维度身份判定：
- 文件名关键词 + 内部文本关键字综合裁决。
- 区分出哪个是 `SI`，哪个是 `DRAFT_BL`。
- 异常场景全面覆盖并抛出精确原因码：
  - 缺少 SI：`MISSING_SI`
  - 缺少 BL：`MISSING_BL`
  - 双缺失：`MISSING_SI` / `DOCUMENT_TYPE_UNCERTAIN`
  - 多份 SI 冲突：`MULTIPLE_SI_CANDIDATES`
  - 多份 BL 冲突：`MULTIPLE_BL_CANDIDATES`

---

## 三、自动化测试执行状态

目前系统中所有测试：