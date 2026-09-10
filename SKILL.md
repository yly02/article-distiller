---
name: article-distiller
description: 将网页、论文、技术报告或本地文档转成面向非技术读者的中文深度解读 HTML；适用于需要来源核验、媒体提取、通俗写作、交互可视化和发布自检的 AI 内容。
---

# 深度文章解读

把原文翻译成一篇普通人能看懂的中文深度文章，不是另写一篇评论。结构跟着原文走，把原文里的事实、演示、数字、工具和限制讲明白；需要补充时只补官方附件和必要解释，不靠文绉绉的重新定性抢戏。
写作标准是：真材实料为底，原文要点为骨，白话为形。写作引擎只有一套，细则以 [references/article-depth.md](references/article-depth.md) 为准：标题是主体加材料支持的人话结果；一句导语加三条速览；一节对应原文一项要点；语气和骨架跟着原文体裁走，不要把分析稿、方法稿写成产品能力清单。

本 Skill 只生成深度文章 HTML，不生成一页纸、小红书卡片或多视图发布壳。GitHub 发布仓库是 [yly02/article-distiller](https://github.com/yly02/article-distiller)，Skill 目录名与入口名均为 `article-distiller`。

## 执行

要求 Python 3.10+。入口是 `scripts/run.py`：

```bash
python3 <skill-root>/scripts/run.py <URL-or-file> -o <output-base>
```

安装后可先运行：

```bash
python3 <skill-root>/scripts/run.py --check
python3 <skill-root>/scripts/run.py --check --no-llm
```

输入支持 URL、TXT、Markdown、HTML、JSON 文章导出、PDF、DOCX 和 DOC。监控系统导出的 `monitoring.article.v2` JSON 可直接作为输入，不必先转成 Markdown。只有正文足够独立成文的 JSON 才能跳过扒页；两三段摘要、残篇或空正文必须回抓 `source_url`。依赖缺失时入口会尝试用当前解释器安装；无法自动处理的 Python、浏览器、LibreOffice、OCR 或 API 配置必须给出可执行提示，不能静默降级。完整参数见 [references/cli.md](references/cli.md)。

第一次使用或需要确认输入方式、产物和失败边界时，读取 [examples/workflows.md](examples/workflows.md)。需要为具体材料选择叙事结构、媒体和交互组件时，按材料类型读取 [examples/casebook.md](examples/casebook.md) 中最接近的 1-3 个案例，并可打开 [examples/articles/](examples/articles/) 里的成品 HTML。示例用于说明决策，不是固定模板，也不能作为事实来源。

默认四步：研究账本 -> 正文写作 -> 主编审校 -> 成稿后统一质量门禁。完整门禁只在审校稿完成后集中检查；只有发现阻断项才追加一次定向修复和复检。`--source-only` 只生成深度文章 prompt 包；`--render` 渲染已有材料包与解读 JSON。不要为了提速默认跳过研究、主编审校或高优先级证据。

## 工作流

1. 读取原文、官方附件、相关仓库和必要的独立来源。网页抓取或媒体发现受阻时，先解决抓取，或使用浏览器限定到文章容器导出正文与 `page-assets.json`。用户 JSON 同时满足“正文足够独立成文”时，直接使用该导出，不要重复扒页；正文过短、明显是摘要或空正文时，必须回抓 `source_url`，不能把残篇当成完整稿。
2. 建立原子主张、数字、实验、案例、来源和未知项组成的研究账本。只有实际读取且独立于发布方的材料才允许形成 `cross_checked`。
3. 先判断体裁并列出原文要点清单，再写成白话章节。一节只讲一项要点：产品节点名演示，分析节讲清原文划界，方法节写清步骤和闸门。不要为了“独特见解”把原文重写成另一篇文章。原文有的能力、框架、演示、数字、工具和限制默认都要覆盖；只有重复装饰或与要点无关时才能省略，并写明理由。材料足够时优先搭出 5-8 个有独立任务的章节。要点讲完再写读者能带走的一步；安全与口径短写，演示、框架和步骤写够。
4. 根据读者要解决的问题选择正文、来源媒体或交互组件。每个章节通常只有一个主视觉；同一事实不得用正文、大表格、数字卡和原图重复铺陈。同一节里两张类比卡不要连着放，各自插到所解释的那句话后面。原页存在多个能力不同的演示时，按“能力覆盖”组合精选媒体；开头依赖的首屏视频必须采用，或记录具体、可核对的省略理由。
5. 主编审校完成后统一运行中文语病、事实与结构、证据与媒体对账、HTML 渲染和浏览器验收；若质量门禁发现阻断项，只做一次定向修复并复检后再交付。

## 按需读取

- 不确定如何处理 URL、本地文件、动态媒体、薄 JSON 或手动渲染：读取 [examples/workflows.md](examples/workflows.md)。
- 不确定某类文章适合什么开头、章节推进或视觉组件：只读取 [examples/casebook.md](examples/casebook.md) 中最接近的 1-3 个案例；需要看成品版式时打开 [examples/articles/](examples/articles/) 对应 HTML。不要复制案例标题、事实或整套结构。
- 开始写作或审稿：读取 [references/article-depth.md](references/article-depth.md)。语病再读 [references/chinese-grammar-review.md](references/chinese-grammar-review.md)；改门禁再读 [references/editorial-quality.md](references/editorial-quality.md)。
- 只有人味边界或对标站“不能抄什么”不清楚时，才再读 [references/human-writing.md](references/human-writing.md) 或 [references/editorial-patterns.md](references/editorial-patterns.md)。
- 扩展来源、深读仓库或检查图片、视频、音频：读取 [references/research-and-media.md](references/research-and-media.md)。
- 修改主张、来源等级、实验、案例或数字结构：读取 [references/evidence-schema.md](references/evidence-schema.md)。
- 选择表格、播放器、关系组件或交互：读取 [references/visual-selection.md](references/visual-selection.md)。
- 用户明确授权生成解释配图：读取 [references/article-imagegen.md](references/article-imagegen.md)。默认不调用生图接口。
- 维护高质量信息源清单：读取 [references/source-registry.md](references/source-registry.md)。

前台结构、标题、速览、来源区、标签和验收细则以 [references/article-depth.md](references/article-depth.md) 的发布验收为准，不要在本文件重复展开。

## 每次任务都要守住的边界

- 只交付深度文章 HTML。
- 不能基于空正文或明显残篇写作。
- 标题先放高认知主体，再放材料支持的人话结果、动作或完整口径数字。不要单独写推荐理由。一分钟速览固定 3 条，内容跟体裁走；文末不渲染打勾清单。
- 文章前台要像有主线的文章，不像审计报告；claim id、质量报告、抓取状态和研究账本只留在运行时。
- 页末来源区只显示来源名称，不提供可点开的详细链接。
- 同一节里两张类比卡不要连着放。
- 客户可见文本必须通过中文语病检查；高置信错误做最小修改。
- 产品发布若把“能看见的能力”当作卖点，必须采用能解释该能力的原页演示；交互表不能替代前后差异或操作视频。
- 介绍页链到的官方定价、模型文档或系统卡要实际读取；不能因为主文没写数字就停在“价格未知”。
- 解读是把原文翻译好懂，不另起炉灶；不省略原文要点和能解释要点的原页材料，也不把文章写成文绉绉的评论。
- 语气跟着原文体裁：产品和研究用说明文，分析用原文框架，方法用步骤和闸门，危机散文才跟文学腔。不把对标站的标题腔、长提示词模板、会员栏或没看见的演示细节写进正文。发散只补官方文档、已看见的演示、参数、定价和原文自带的方法骨架。

## 交付与数据

只交付 HTML，并说明实际读取的独立材料以及仍仅来自发布方的结论。运行时数据默认写入 `~/.article-distiller/`，可由 `ARTICLE_DISTILLER_DATA_DIR` 覆盖；不得把历史索引、密钥或个人绝对路径打入发行包。

发布前运行 `scripts/release_check.py`、核心行为测试、Python 编译和 Skill validator。最终审计与阶段耗时写入运行时缓存中的 `final-quality.json`，不暴露到文章前端；发布检查必须从独立解包目录验证 `scripts/run.py`，不能只测试当前工作树。
