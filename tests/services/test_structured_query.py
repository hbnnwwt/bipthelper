import sys
import os
import re
from datetime import datetime, timedelta

# 确保 backend 目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.structured_query import (
    classify,
    extract_date_range,
    build_structured_query,
    build_menu_query,
    format_structured_result,
)


# ---------- classify ----------

def test_classify_rag():
    assert classify("红烧肉是什么菜？") == "rag"

def test_classify_structured():
    assert classify("哪个菜出现最多？") == "structured"

def test_classify_structured_stat_only():
    assert classify("统计一下出现次数") == "structured"

def test_classify_hybrid():
    assert classify("哪个菜最多，介绍一下它的做法") == "hybrid"

def test_classify_default_rag():
    # 没有任何关键词，默认 rag
    assert classify("明天食堂开门吗") == "rag"


# ---------- extract_date_range ----------

def test_extract_date_range_month_only():
    start, end = extract_date_range("3月以来最受欢迎的菜")
    today = datetime.now().date()
    assert start == f"{today.year}-03-01"
    assert end == today.isoformat()

def test_extract_date_range_month_day_since():
    start, end = extract_date_range("4月1日以来的午餐统计")
    today = datetime.now().date()
    assert start == f"{today.year}-04-01"
    assert end == today.isoformat()

def test_extract_date_range_full_since():
    start, end = extract_date_range("2026年3月15日以来哪个菜最多")
    assert start == "2026-03-15"

def test_extract_date_range_year_month():
    start, end = extract_date_range("2026年2月的菜谱统计")
    assert start == "2026-02-01"

def test_extract_date_range_default_30_days():
    start, end = extract_date_range("最近哪个菜最多")
    today = datetime.now().date()
    expected_start = (today - timedelta(days=30)).isoformat()
    assert start == expected_start
    assert end == today.isoformat()


# ---------- build_structured_query ----------

def test_build_structured_query_returns_none_without_category():
    result = build_structured_query("哪个菜最多", "", "教工食堂菜谱")
    assert result is None

def test_build_structured_query_returns_none_without_sub_category():
    result = build_structured_query("哪个菜最多", "食堂", "")
    assert result is None

def test_build_structured_query_menu():
    result = build_structured_query("哪个菜最多", "食堂", "教工食堂菜谱")
    assert result is not None
    assert "sql" in result
    assert "params" in result
    assert "dimension" in result

def test_build_structured_query_unknown_sub_category():
    result = build_structured_query("哪个菜最多", "食堂", "未知分类")
    assert result is None


# ---------- build_menu_query ----------

def test_build_menu_query_no_filter():
    result = build_menu_query("哪个菜最多", "2026-01-01", "2026-04-15")
    assert result["dimension"] == "dish_name"
    assert result["params"] == ["2026-01-01", "2026-04-15"]
    assert "GROUP BY dish_name" in result["sql"]

def test_build_menu_query_meal_filter():
    result = build_menu_query("午餐哪个菜最多", "2026-01-01", "2026-04-15")
    assert "午餐" in result["params"]
    assert "meal_type = ?" in result["sql"]

def test_build_menu_query_category_filter():
    result = build_menu_query("热菜哪个最多", "2026-01-01", "2026-04-15")
    assert "热菜" in result["params"]
    assert "dish_category = ?" in result["sql"]

def test_build_menu_query_meal_and_category_filter():
    result = build_menu_query("晚餐凉菜哪个最多", "2026-01-01", "2026-04-15")
    assert "晚餐" in result["params"]
    assert "凉菜" in result["params"]

def test_build_menu_query_limit():
    result = build_menu_query("哪个菜最多", "2026-01-01", "2026-04-15")
    assert "LIMIT 10" in result["sql"]


# ---------- format_structured_result ----------

def test_format_structured_result_empty():
    assert format_structured_result([], "哪个菜最多", "dish_name") == "未找到符合条件的记录。"

def test_format_structured_result_basic():
    rows = [{"dish_name": "红烧肉", "cnt": 12, "dates": "2026-03-01,2026-03-02"}]
    text = format_structured_result(rows, "哪个菜最多", "dish_name")
    assert "红烧肉" in text
    assert "12" in text

def test_format_structured_result_many_dates():
    dates = ",".join([f"2026-03-{i:02d}" for i in range(1, 10)])
    rows = [{"dish_name": "红烧肉", "cnt": 9, "dates": dates}]
    text = format_structured_result(rows, "哪个菜最多", "dish_name")
    assert "等9天" in text

def test_format_structured_result_no_dates():
    rows = [{"dish_name": "土豆丝", "cnt": 5, "dates": ""}]
    text = format_structured_result(rows, "哪个菜最多", "dish_name")
    assert "土豆丝" in text
    assert "5" in text


if __name__ == "__main__":
    # 简单运行所有测试函数
    import traceback
    passed = 0
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                traceback.print_exc()
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
