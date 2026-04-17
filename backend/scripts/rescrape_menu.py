"""
重新提取所有菜谱文档的 structured 数据。

用法：
    cd E:/code/bipthelper
    python backend/scripts/rescrape_menu.py

清除旧 menu_items，用新 parser（含 section）重新提取所有 sub_category="生活服务" 的文档。
"""
import sys
sys.path.insert(0, "backend")

from database import create_session
from models.document import Document
from models.menu_item import MenuItem
from services.parsers.menu_parser import parse_menu_content
from sqlmodel import select, delete

def main():
    print("[rescrape] 开始重新提取菜谱...")

    with create_session() as s:
        # 查所有菜谱文档
        docs = s.exec(
            select(Document).where(Document.sub_category == "生活服务")
        ).all()
        print(f"[rescrape] 找到 {len(docs)} 篇菜谱文档")

        # 清除旧数据
        s.exec(delete(MenuItem))
        s.commit()
        print("[rescrape] 已清空 menu_items 表")

        total_items = 0
        for doc in docs:
            items = parse_menu_content(
                content=doc.content,
                doc_id=doc.id,
                category=doc.category or "",
                sub_category=doc.sub_category or "",
                source_url=doc.url,
            )
            for item in items:
                s.add(item)
            total_items += len(items)

            # 每 50 篇打印进度
            if total_items % 500 < 100:
                print(f"[rescrape] 已处理 {total_items} 条记录...")

        s.commit()
        print(f"[rescrape] 完成！共提取 {total_items} 条 menu_items")

if __name__ == "__main__":
    main()
