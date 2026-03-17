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

## 当前采集进度（2026-03-17）

### 爬虫平台

| 平台 | 已采集 | 存储路径 |
|------|--------|---------|
| Coursera | 2,011 门 | `course_scraper/data/raw/coursera/` |
| edX | 1,000 门 | `course_scraper/data/raw/edx/` |
| 中国大学 MOOC | 4,650 门 | `course_scraper/data/raw/mooc_cn/` |
| **爬虫合计** | **7,661 门** | |

### 开放数据集（已下载）

#### MOOCCubeX（清华 AMiner，XuetangX 学堂在线）

存储路径：`mooccubex/`

| 文件 | 大小 | 内容 | 状态 |
|------|------|------|------|
| `entities/course.json` | 43MB | 3,781 门课程（名称/领域/先修/简介） | ✅ |
| `entities/video.json` | 592MB | 视频元数据 | ✅ |
| `entities/problem.json` | 96MB | 习题内容 | ✅ |
| `entities/user.json` | 769MB | 用户信息 | ✅ |
| `entities/comment.json` | 2.2GB | 8,395,141 条课程评论 | ✅ |
| `entities/reply.json` | 50MB | 评论回复 | ✅ |
| `entities/concept.json` | 155MB | 知识概念图谱 | ✅ |
| `entities/school.json` | 640KB | 学校信息 | ✅ |
| `entities/teacher.json` | 9.1MB | 教师信息 | ✅ |
| `relations/user-video.json` | 3.0GB | 用户×视频观看记录 | ✅ |
| `relations/user-problem.json` | 21GB | 用户×习题作答记录 | ✅ |
| `relations/user-xiaomu.json` | 9.7MB | 学生学习轨迹 | ✅ |
| `relations/exercise-problem.txt` | 129MB | 练习题映射 | ✅ |
| `relations/course-field.json` | 64KB | 课程领域映射 | ✅ |
| `relations/concept-course/video/problem/comment/other.txt` | ~79MB | 知识点关系链 | ✅ |
| `prerequisites/cs.json` | 86MB | CS 先修关系图 | ✅ |
| `prerequisites/math.json` | 59MB | 数学先修关系图 | ✅ |
| `prerequisites/psy.json` | 133MB | 心理学先修关系图 | ✅ |

#### Kaggle / 公开数据集

存储路径：`datasets/`

| 数据集 | 路径 | 大小 | 内容 | 用途 |
|--------|------|------|------|------|
| OULAD | `datasets/oulad/` | 488MB | 英国开放大学 32,593 名学生完整行为+最终成绩（7个CSV） | 质量 ground truth label |
| Coursera Reviews | `datasets/coursera_reviews/` | 310MB | 1,501,261 条评论+评分，624 门课程 | 英文质量信号 |
| Coursera Meta 2024 | `datasets/coursera_meta/` | 11MB | 8,472 门课程元数据（清洗版+原始版） | 大规模元数据 |
| EdX + Coursera + Udemy 合并 | `datasets/multi_platform/` | 196MB | 三平台课程 JSON，含处理脚本 | 跨平台元数据 |
| EdX Courses 2021 | `datasets/edx_meta/` | 1.1MB | 836 门 EdX 课程 | EdX 补充 |
| Udemy Courses | `datasets/udemy_kaggle/` | 680KB | 3,682 门课程（评分/价格/学员数） | Udemy 样本 |
| ASSISTments 2012-2013 | `datasets/assistments/` | 1.5GB | 学生答题行为序列（知识追踪） | 行为特征基准 |
| KDD Cup 2015 | `datasets/kddcup2015/` | 用户手动下载 | XuetangX 辍课预测数据集 | 辍课标签 |
| EdNet KT3-4 | `datasets/ednet/` | 下载中（目标 2.6GB） | 1.3 亿条学习交互记录 | 大规模行为数据 |

### 数据汇总

| 类别 | 规模 |
|------|------|
| 课程元数据 | ~2 万门（含爬虫 + MOOCCubeX + Kaggle 数据集） |
| 用户评论 | ~1,000 万条（MOOCCubeX 839 万 + Coursera 150 万） |
| 用户行为记录 | ~数亿条（user-video 3GB + user-problem 21GB + OULAD + ASSISTments） |
| 知识图谱概念 | ~20 万个概念节点 |

## 已知问题

- `reviews`、`rating`、`learning_goals` 字段目前大部分为空，需要登录态 Cookie 或额外接口调用
- Coursera 大纲接口（`onDemandCourseMaterials.v2`）响应结构存在多种变体，已做兼容处理
- EdNet 下载中（`datasets/ednet/download.log` 可查看进度），下载完成后需解压
- KDD Cup 2015 需手动放入 `datasets/kddcup2015/`（需在 Kaggle 页面接受比赛规则后下载）
