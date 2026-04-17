"""
附件解析器（Windows 环境）
支持 .docx / .pdf / .doc（需安装 Microsoft Office）
"""
import logging
from pathlib import Path
from typing import Optional

import docx
try:
    import fitz  # pymupdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    try:
        import PyPDF2  # 回退方案
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

import win32com.client

logger = logging.getLogger(__name__)


def parse_attachment(file_path: Path) -> Optional[str]:
    """解析附件，返回纯文本内容；失败返回 None"""
    suffix = Path(file_path).suffix.lower()
    try:
        if suffix == ".docx":
            return _parse_docx(file_path)
        elif suffix == ".doc":
            return _parse_doc(file_path)
        elif suffix == ".pdf":
            return _parse_pdf(file_path)
        else:
            logger.warning(f"Unsupported attachment type: {suffix}")
            return None
    except Exception as e:
        logger.error(f"Failed to parse attachment {file_path}: {e}")
        return None


def _parse_docx(path: Path) -> str:
    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _parse_pdf(path: Path) -> str:
    if PDF_AVAILABLE:
        try:
            doc = fitz.open(str(path))
            texts = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(texts)
        except Exception:
            pass
    # PyPDF2 回退
    try:
        import PyPDF2
        texts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


def _parse_doc(path: Path) -> Optional[str]:
    """使用 Word COM 自动化解析 .doc（Windows + Office 必备）"""
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(path))
            text = doc.Content.Text
            doc.Close(SaveChanges=False)
            return text.strip()
        finally:
            word.Quit()
    except Exception as e:
        logger.warning(f"Word COM parse failed for {path}: {e}")
        return None