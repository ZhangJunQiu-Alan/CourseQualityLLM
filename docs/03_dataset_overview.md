# 数据集全景与建模支撑分析

> 更新时间：2026-03-17

## 一、数据集功能分类

### 1. 课程元数据（LLM 评估的核心输入）

| 数据集 | 课程数 | 关键字段 | 用途 |
|--------|--------|---------|------|
| MOOCCubeX `course.json` | 3,781 | 课程名、领域、先修要求、简介 | 中文 MOOC 核心，直接用于 prompt |
| 中国大学 MOOC 爬虫 | 4,650 | 描述、大纲、评分、学员数 | 中文平台主力 |
| Coursera 爬虫 | 2,011 | 完整元数据含大纲 | 英文平台主力 |
| edX 爬虫 | 1,000 | 完整元数据 | 英文平台补充 |
| Coursera Meta 2024 | 8,472 | 标题/机构/技能/评分 | Coursera 大规模元数据 |
| EdX Meta 2021 | 836 | 标题/大学/科目/价格 | edX 补充 |
| Multi-platform 合并 | 数万条 | EdX+Coursera+Udemy 三平台 JSON | 跨平台统一元数据 |
| Udemy Kaggle | 3,682 | 标题/价格/评分/学员数/评论数 | Udemy 代表性样本 |

**可直接用于 LLM 评估 prompt 的课程内容合计约 2 万门**

---

### 2. 用户评论（质量信号 / Fine-tune Label）

| 数据集 | 评论数 | 字段 | 用途 |
|--------|--------|------|------|
| MOOCCubeX `comment.json` | **839 万条** | 评论文本、用户 ID、课程 ID | 中文评论情感分析 |
| MOOCCubeX `reply.json` | ~50 万条 | 回复文本 | 评论上下文补充 |
| Coursera Reviews | **150 万条** | 评论文本、1-5 星评分 | 英文评论 + 质量标签 |

> 评分 + 评论组合是最直接的质量代理变量，可用作 LLM fine-tune 监督信号。

---

### 3. 用户行为数据（质量代理变量）

| 数据集 | 规模 | 关键字段 | 用途 |
|--------|------|---------|------|
| MOOCCubeX `user-video.json` | 3GB | 用户×视频观看记录 | 完课率、观看深度 |
| MOOCCubeX `user-problem.json` | 21GB | 用户×习题作答记录 | 答题正确率、学习效果 |
| OULAD `studentVle.csv` | 433MB / ~1000 万条 | 学生×学习资源交互次数 | 参与度 → 质量代理 |
| OULAD `studentAssessment.csv` | 5.4MB | 作业成绩、提交时间 | 成绩 → 质量结果变量 |
| KDD Cup 2015 | 待放入 | XuetangX 学生辍课标签 | 辍课预测 → 质量信号 |
| ASSISTments 2012-2013 | 1.5GB | 答题序列、知识点、正误 | 知识追踪基准 |
| EdNet KT3-4 | 2.6GB（下载中） | 1.3 亿条学习交互 | 大规模行为数据 |

---

### 4. 知识图谱（可解释性增强）

| 数据集 | 规模 | 用途 |
|--------|------|------|
| MOOCCubeX `concept.json` | ~20 万概念节点 | 课程知识点覆盖度特征 |
| `concept-course/video/problem/comment.txt` | 全链路映射 | 知识点 → 课程/视频/习题对齐 |
| `prerequisites/cs, math, psy.json` | CS + 数学 + 心理学 | 先修关系图，知识链完整性评估 |

---

### 5. 结构化学习结果（Ground Truth Label）

| 数据集 | 内容 | 用途 |
|--------|------|------|
| OULAD `studentInfo.csv` | 最终通过 / 失败 / 撤课 | 课程质量的强监督 label |
| OULAD `studentAssessment.csv` | 各次作业成绩 | 细粒度学习效果 |
| MOOCCubeX `user-xiaomu.json` | 学生学习轨迹 | 学习路径分析 |

---

## 二、三条建模路线

### 路线 A：纯文本 → LLM Zero/Few-shot 评估

```
输入：course.json + 爬虫元数据（课程描述 + 大纲）
标签：Coursera Reviews 评分 + OULAD 通过率
规模：~2 万门课，150 万条评论
方法：Zero-shot / Few-shot prompt（基于 QM 8 大维度设计）
```

**优点**：实现最快，直接产出论文基线结果
**缺点**：仅用文本，缺乏行为信号

---

### 路线 B：行为特征 → 质量预测

```
输入：user-video + user-problem + OULAD studentVle
标签：OULAD final_result + KDD Cup 辍课标签
规模：千万级交互记录
方法：特征工程（完课率、正确率、参与度） + 传统 ML / BERT
```

**优点**：强监督信号，行为特征客观
**缺点**：需要大量用户数据，冷启动问题

---

### 路线 C：多模态融合（论文最终方案）

```
文本特征（路线A）
  + 行为特征（路线B）
  + 知识图谱特征（先修链完整性、概念覆盖度）
→ LLM 生成多维度评分 + 改进建议
```

**评估维度**（对齐 QM Rubric 8 大标准）：
1. 课程概览与介绍
2. 学习目标清晰度
3. 评估与测量
4. 教学材料质量
5. 学习活动与互动
6. 课程技术
7. 学习者支持
8. 无障碍与可用性

---

## 三、数据规模总览

| 维度 | 规模 |
|------|------|
| 课程元数据 | ~2 万门（14 个来源） |
| 用户评论 | ~1,000 万条 |
| 用户行为记录 | 数亿条（user-problem 21GB + user-video 3GB + OULAD + ASSISTments） |
| 知识图谱概念 | ~20 万节点 |
| 总数据量 | ~30GB+ |
