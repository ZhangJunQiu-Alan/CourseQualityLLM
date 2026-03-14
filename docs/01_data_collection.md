# 数据采集模块文档

## 概述

本模块负责从三个主流 MOOC 平台批量爬取课程数据，为后续 LLM 课程质量评估提供原始语料。

## 平台覆盖

| 平台 | 模块文件 | API 基址 | 最大爬取量 |
|------|----------|----------|-----------|
| Coursera | `scrapers/coursera.py` | `https://api.coursera.org/api` | 2000 门 |
| edX | `scrapers/edx.py` | `https://www.edx.org/api/catalog/v2` | 1000 门 |
| 中国大学 MOOC | `scrapers/mooc_china.py` | `https://www.icourse163.org` | 2000 门 |

## 数据字段

每条课程记录包含以下字段：

```json
{
  "course_id":      "平台内唯一 ID",
  "platform":       "coursera | edx | mooc_cn",
  "title":          "课程名称",
  "slug":           "URL 标识符",
  "description":    "课程简介",
  "learning_goals": ["学习目标列表"],
  "prerequisites":  "先修要求",
  "difficulty":     "BEGINNER | INTERMEDIATE | ADVANCED",
  "duration":       "建议学习时长",
  "language":       "语言代码（如 en, zh）",
  "url":            "课程页面 URL",
  "instructors":    [{"name": "", "title": "", "institution": ""}],
  "institutions":   ["开课机构"],
  "rating":         {"average": 0.0, "count": 0},
  "syllabus":       [{"week": 1, "title": "", "description": "", "duration": ""}],
  "reviews":        [{"rating": 0, "text": "", "date": ""}]
}
```

## 存储结构

```
course_scraper/data/
├── raw/
│   ├── coursera/   # 每门课程一个 JSON 文件（以 course_id 命名）
│   ├── edx/
│   └── mooc_cn/
└── db/
    └── courses.db  # SQLite 汇总数据库，去重入库
```

## 运行方式

```bash
# 环境准备（首次）
pip install -r requirements.txt
python -m playwright install chromium

# 爬取单个平台
python main.py --platform coursera
python main.py --platform edx
python main.py --platform mooc_cn

# 爬取全部平台
python main.py

# 查看统计
python main.py --stats
```

## 认证配置（Coursera）

Coursera 登录后可获取更完整的数据（大纲详情、评论等）。将 Cookie 写入 `.env`：

```
COURSERA_COOKIE=CAUTH=xxx; CSRF3-Token=xxx; ...
```

`config.py` 会自动读取并注入请求头（含 `X-CSRFToken`）。

## 当前采集进度（2026-03-14）

| 平台 | 已采集 |
|------|--------|
| Coursera | 2,011 门 |
| edX | 1,000 门 |
| 中国大学 MOOC | 4,650 门 |
| **合计** | **7,661 门** |

## 已知问题

- `reviews`、`rating`、`learning_goals` 字段目前大部分为空，需要登录态 Cookie 或额外接口调用
- Coursera 大纲接口（`onDemandCourseMaterials.v2`）响应结构存在多种变体，已做兼容处理
