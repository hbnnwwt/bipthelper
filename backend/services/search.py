import meilisearch
from config import get_settings

settings = get_settings()

_client = None

def get_client() -> meilisearch.Client:
    global _client
    if _client is None:
        _client = meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY)
    return _client

def get_index():
    client = get_client()
    try:
        index = client.get_index(settings.MEILISEARCH_INDEX)
    except meilisearch.errors.MeilisearchApiError:
        # 索引不存在，创建它
        client.create_index(settings.MEILISEARCH_INDEX, {"primaryKey": "id"})
        index = client.get_index(settings.MEILISEARCH_INDEX)
        # 配置可筛选字段
        index.update_filterable_attributes(["category", "department", "publish_date"])
        index.update_sortable_attributes(["publish_date", "title"])
        # searchable_attributes 顺序决定匹配优先级：title 在前 = 优先匹配标题
        index.update_searchable_attributes(["title", "content"])
    return index

def index_document(doc):
    """将文档添加到搜索索引"""
    index = get_index()
    doc_dict = {
        "id": doc.id,
        "url": doc.url,
        "title": doc.title,
        "content": doc.content,
        "category": doc.category or "",
        "department": doc.department or "",
        "publish_date": doc.publish_date or "",
    }
    index.add_documents([doc_dict])

def delete_document_from_index(doc_id: str):
    """从搜索索引删除文档"""
    index = get_index()
    index.delete_document(doc_id)

def _escape_filter(value: str) -> str:
    """转义 MeiliSearch 过滤字符串中的双引号"""
    return value.replace('"', '\\"')

def search_documents(query: str, category: str = None, department: str = None,
                     start_date: str = None, end_date: str = None,
                     page: int = 1, page_size: int = 20):
    """搜索文档"""
    index = get_index()

    filters = []
    if category:
        filters.append(f'category = "{_escape_filter(category)}"')
    if department:
        filters.append(f'department = "{_escape_filter(department)}"')
    if start_date:
        filters.append(f'publish_date >= "{_escape_filter(start_date)}"')
    if end_date:
        filters.append(f'publish_date <= "{_escape_filter(end_date)}"')

    filter_str = " AND ".join(filters) if filters else None

    result = index.search(
        query,
        {
            "limit": page_size,
            "offset": (page - 1) * page_size,
            "filter": filter_str,
            "sort": ["publish_date:desc"],
            "attributesToRetrieve": ["id", "title", "content", "category", "department", "publish_date", "url"],
            "attributesToHighlight": ["title", "content"],
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
        }
    )

    return {
        "total": result["estimatedTotalHits"],
        "results": result["hits"],
        "page": page,
        "page_size": page_size,
    }