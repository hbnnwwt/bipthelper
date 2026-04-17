import json
import logging
import re
from .client import get_provider_config, call_llm

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_TEMPLATE = """你是一个学校信息分类专家。根据以下文章标题，判断它属于哪个分类。

可选分类：{categories}
标题：{title}

请返回JSON格式，只包含 categories 数组，不要其他内容。
格式：{{"categories": ["分类1", "分类2"]}}"""

DEFAULT_CATEGORIES = "通知公告,规章制度,部门文件,工作动态,学术活动,招标信息,人事信息,财务信息,后勤保障,校园活动"

def get_active_scene():
    """获取第一个激活的分类场景"""
    from models.ai_provider import AICategoryScene
    from database import engine
    from sqlmodel import Session, select

    with Session(engine) as session:
        scene = session.exec(
            select(AICategoryScene).where(AICategoryScene.is_active == True)
        ).first()
        return scene

def categorize_article(title: str) -> list[str]:
    """
    使用 LLM 对文章进行分类，返回分类标签列表。
    如果没有配置 AI 场景，返回空列表。
    """
    scene = get_active_scene()
    if not scene:
        return []

    try:
        provider_config = get_provider_config(scene.provider_id)
        if not provider_config or not provider_config.get("api_key"):
            logger.warning(f"Provider {scene.provider_id} not configured for categorization")
            return []

        # 构建 prompt
        categories = scene.default_categories or DEFAULT_CATEGORIES
        prompt = scene.prompt_template or DEFAULT_PROMPT_TEMPLATE

        user_content = prompt.format(
            categories=categories,
            title=title or "",
        )

        messages = [{"role": "user", "content": user_content}]
        model = scene.model or None

        result = call_llm(scene.provider_id, messages, model=model)

        # 解析 JSON 返回
        categories = _parse_json_response(result)
        if categories:
            logger.info(f"AI categorized article '{title[:30]}' as: {categories}")

        return categories

    except Exception as e:
        logger.error(f"AI categorization failed for '{title[:30]}': {e}")
        return []

def _parse_json_response(text: str) -> list[str]:
    """从 LLM 返回文本中解析 JSON 分类列表"""
    if not text:
        return []

    # 尝试直接解析
    try:
        data = json.loads(text)
        cats = data.get("categories", [])
        if isinstance(cats, list):
            return [str(c).strip() for c in cats if c]
    except json.JSONDecodeError:
        pass

    # 尝试从文本中提取 JSON
    match = re.search(r'\{[^{}]*"categories"\s*:\s*\[[^\]]+\][^{}]*\}', text)
    if match:
        try:
            data = json.loads(match.group())
            cats = data.get("categories", [])
            if isinstance(cats, list):
                return [str(c).strip() for c in cats if c]
        except json.JSONDecodeError:
            pass

    # 尝试提取数组
    match = re.search(r'\["[^"]+"(?:\s*,\s*"[^"]+")*\]', text)
    if match:
        try:
            cats = json.loads(match.group())
            return [str(c).strip() for c in cats if c]
        except json.JSONDecodeError:
            pass

    logger.warning(f"Failed to parse categorization response: {text[:100]}")
    return []
