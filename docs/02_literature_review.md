# 文献综述：在线课程质量评估

> 调研时间：2026-03-14

## 研究定位

本研究将「多平台大规模爬取的 MOOC 元数据（大纲、描述、评论）」与「LLM 结构化质量评估」相结合，目前尚无完全相同的工作。最接近的三篇文献如下：

| 论文 | 相似点 | 差异点 |
|------|--------|--------|
| Yuan & Hu (arXiv 2024) | 同样用 LLM 评价课程质量 | 评的是课堂讨论，不是爬取的 MOOC 元数据 |
| Springer 2024（LDA+AHP） | 同样用 Coursera 评论做质量评估 | 传统 NLP，非 LLM |
| CHB 2021（设计+情感分析） | 结合课程设计分析与学生评论 | 手动分析 18 门课，未自动化 |

---

## 相关文献

### 一、LLM 用于课程/教育评估

**1. An Exploration of Higher Education Course Evaluation by Large Language Models**
- 作者：Bo Yuan, Jiazi Hu｜年份：2024｜来源：arXiv:2411.02455
- 用代表性 LLM 在微观（课堂讨论）和宏观（课程整体评价）两个层级自动评价课程，发现微调和 Prompt 工程显著提升准确性。
- 链接：https://arxiv.org/abs/2411.02455

**2. Large Language Model-Powered Automated Assessment: A Systematic Review**
- 年份：2025｜来源：Applied Sciences, MDPI
- 综述 49 篇研究（2018–2024），GPT-4 与人类评分者一致性高（QWK 最高 0.99）。
- 链接：https://www.mdpi.com/2076-3417/15/10/5683

**3. Leveraging Prompt-Based LLMs for Automated Scoring and Feedback Generation in Higher Education**
- 年份：2025｜来源：ScienceDirect
- GPT-4 在反馈可读性、一致性等维度优于 GPT-3.5 和人类讲师；Prompt 质量和评分细则对准确性影响显著。
- 链接：https://www.sciencedirect.com/science/article/pii/S0360131525002799

**4. A Large Language Model Approach to Educational Survey Feedback Analysis**
- 年份：2024｜来源：IJAIED, Springer
- 用 LLM 大规模分析教育调查反馈，替代耗时的人工编码，可从非结构化文本中提取结构化主题和情感。
- 链接：https://link.springer.com/article/10.1007/s40593-024-00414-0

---

### 二、MOOC 课程质量自动评估（NLP/文本挖掘）

**5. Leveraging Text Mining and AHP for the Automatic Evaluation of Online Courses**
- 年份：2024｜来源：IJMLC, Springer
- 结合 LDA 主题建模与层次分析法（AHP）自动评估在线课程，从 51,637 条评论中提炼出 **8 个核心评价维度**：assessment、content、effort、usefulness、enjoyment、faculty、interaction、structure。数据来自 Coursera。
- 链接：https://link.springer.com/article/10.1007/s13042-024-02203-6

**6. Understanding Learners' Perception of MOOCs Based on Review Data Analysis**
- 年份：2022｜来源：Future Internet, MDPI
- 分析 186,738 条评论，归纳出学习者关注的 8 类维度：课程质量、学习资源、教师、关系、考核、学习过程、平台、工具。
- 链接：https://www.mdpi.com/1999-5903/14/8/218

**7. MOOC Evaluation System Based on Deep Learning**
- 年份：2022｜来源：IRRODL
- 用深度神经网络（回归）从学习行为日志预测学生满意度，解决问卷响应率低的问题。
- 链接：https://www.irrodl.org/index.php/irrodl/article/view/5417

**8. Sentiment Analysis on MOOC Evaluations: A Text Mining and Deep Learning Approach**
- 年份：2021｜来源：CAE, Wiley
- 评估多种监督学习、集成学习、深度学习方法在 66,000 条 MOOC 评论情感分析上的表现。
- 链接：https://onlinelibrary.wiley.com/doi/10.1002/cae.22253

**9. Analyzing Instructional Design Quality and Students' Reviews of 18 Top MOOCs**
- 年份：2021｜来源：Computers in Human Behavior
- 将教学设计系统分析（十原则框架）与学生评论情感分析结合，发现教学设计质量与 MOOC 排名正相关。
- 链接：https://www.sciencedirect.com/science/article/abs/pii/S1096751621000191

**10. Perceived MOOC Satisfaction: A Review Mining Approach Using Fine-Tuned BERTs**
- 年份：2025｜来源：Computers in Human Behavior Reports
- 用微调 BERT 模型挖掘 MOOC 学习者满意度，精度高于传统机器学习。
- 链接：https://www.sciencedirect.com/science/article/pii/S2666920X25000062

---

### 三、MOOC 质量框架与指标体系

**11. Quality Criteria in MOOC: Comparative and Proposed Indicators**
- 年份：2022｜来源：PMC / PLoS One
- 德尔菲法结合 ENQA 欧洲质量保证标准，提出 MOOC 质量指标体系，涵盖教学设计、内容、考核、学习者支持、技术、产出 6 大类。
- 链接：https://pmc.ncbi.nlm.nih.gov/articles/PMC9721481/

**12. Towards Quality Assurance in MOOCs: A Comprehensive Review and Micro-Level Framework**
- 年份：2024｜来源：IRRODL
- 综述 2018–2022 年 MOOC 质量文献，提出「presage–process–product」微观框架，验证四维度：教学质量、组织质量、技术质量、社交质量。
- 链接：https://www.irrodl.org/index.php/irrodl/article/view/7544

**13. A Systematic Literature Review on the Quality of MOOCs**
- 年份：2021｜来源：Sustainability, MDPI
- 综述 MOOC 质量维度：内容、教学法、考核、学习者参与、可及性、平台质量。
- 链接：https://www.mdpi.com/2071-1050/13/11/5817

**14. The Quality Appraisal of MOOCs Using Decision Support Model**
- 年份：2025｜来源：Complex & Intelligent Systems, Springer
- 多准则决策模型用于 MOOC 质量评估，结合专家判断与数据驱动方法。
- 链接：https://link.springer.com/article/10.1007/s40747-025-01927-4

---

### 四、中文研究

**15. MOOC 课程高质量发展的飞轮效应**
- 来源：SciOpen（中文期刊）
- 从中文 MOOC 评论中挖掘质量因素，建立 **7 个一级指标 + 35 个二级指标**体系：教学风格、用户体验、课程内容、教学设计、信息呈现、教学方法等。

**16. 欧洲 MOOC 教育质量评价方法及启示**
- 作者：刘璐、刘志敏、罗英姿（南京农业大学）｜来源：开放教育研究
- 综述欧洲 MOOC 质量评价的输入、过程、产出三类要素，提出对中国情境的启示。

---

## 汇总：文献中反复出现的核心评价维度

| 维度 | 对应本研究可用字段 |
|------|------------------|
| 课程内容（准确性、深度、时效性） | `description`, `syllabus` |
| 教学/课程设计（结构、目标清晰度） | `syllabus`, `learning_goals` |
| 教师质量（专业度、表达能力） | `instructors` |
| 考核与作业 | `syllabus`（周内容描述） |
| 学习者参与与互动 | `reviews` |
| 学习产出与实用性 | `learning_goals`, `reviews` |
| 平台与技术体验 | `reviews` |
| 学习所需付出（难度匹配） | `difficulty`, `duration` |
