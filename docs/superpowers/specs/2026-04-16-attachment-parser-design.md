# 修复设计文档：附件解析支持

## 问题描述
- 在当前数据库中，817 篇文档的内容仅包含版权页脚（<200 字符），实际内容存储为 `.doc` 或 `.pdf` 附件。
- 爬虫的 `extract_main_content` 仅解析 HTML 文本，无法提取附件正文，导致这些文档在 RAG 检索中无有效向量，搜索失败。

## 修复方案
扩展爬虫，在提取完 HTML 内容后：
1. 检测页面是否“仅包含页脚”（即附件型页面）
2. 查找 `<a>` 标签中的附件链接（`.doc/.docx/.pdf`）
3. 下载附件并调用解析器提取文本
4. 将附件文本作为主内容，与 HTML 标题合并入库

## 技术选型（Windows 环境）
| 格式 | 解析库 | 安装命令 |
|---|---|---|
| `.docx` | `python-docx` | `pip install python-docx` |
| `.pdf` | `pymupdf` (fitz) | `pip install pymupdf` |
| `.doc` | `pywin32` + Word COM | `pip install pywin32`（需本地安装 Microsoft Office） |

## 文件修改
1. **新增文件**：`backend/services/attachment_parser.py`
   - 包含 `parse_attachment()` 函数，支持 `.docx`/`.pdf`/`.doc`
2. **修改文件**：`backend/services/crawler.py`
   - 在 `extract_article` 逻辑后增加附件检测与下载解析步骤
   - 新增辅助函数：`_is_attachment_only`, `_find_attachment_link`, `_download_and_parse`

## 数据流
```
爬取 HTML → 提取标题 & 正文 → 检测是否仅页脚
    ↓ 是
查找附件链接 → 下载 → 解析文本 → 合并内容 → 入库
    ↓ 否
直接入库
```

## 注意事项
- **Office 依赖**：`.doc` 解析依赖本地安装的 Microsoft Office。如生产环境无 Office，可改用 `antiword`（Linux）或跳过解析。
- **性能**：首次加载 Word COM 有启动开销，建议批量解析时增加队列/缓存。
- **错误处理**：解析失败时保留原始 HTML 作为回退，不中断爬虫流程。

## 后续优化（可选）
- 添加 `antiword` 支持 `.doc`（跨平台）
- 增加解析结果缓存，减少重复下载
- 使用 `PyPDF2` 或 `pymupdf` 的 OCR 功能处理扫描件 PDF
