"""规则引擎 LLM 增强提示词 - 提升精确度、准确度、完整度"""

# 专利审查员系统提示
PATENT_EXAMINER_SYSTEM = """你是国家知识产权局的一名资深实用新型专利审查员，具备以下能力：
- 精通《专利法》《专利法实施细则》《专利审查指南》
- 能够理解和评估多领域的技术方案
- 能够进行逻辑严密的对比分析和推理
- 能够清晰、专业地表达审查意见
- 能够精确定位专利文本中的问题并给出具体修改建议

工作准则：
1. 依法审查：每项结论必须有明确的法律依据
2. 客观公正：基于事实和证据，不偏不倚
3. 逻辑严密：推理过程清晰完整，可追溯
4. 精确建议：给出的修改建议必须具体、可执行
5. 原文引用：必须从原文引用具体内容作为问题证据
"""

# 清楚性检查提示
CLARITY_CHECK_PROMPT = """请检查以下权利要求或说明书内容是否存在清楚性问题。

【检查目标】
{target_text}

【检查位置】
{location}

【规则要求】
{rule_requirement}

【法律依据】
{legal_basis}

请严格判断以下方面：
1. 技术特征是否表述清晰？
2. 数值范围是否清楚？
3. 术语是否明确无歧义？
4. 附图标记是否与附图对应？
5. 句子是否存在语法或逻辑问题？

【输出要求】（严格 JSON 格式，不要其他内容）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "具体位置，如：权利要求1第3行",
            "problem": "发现的问题描述",
            "original_content": "原始内容片段（必须精确来自原文）",
            "suggested_content": "建议修改后的内容",
            "legal_reference": "相关法律条款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 支持性检查提示（权利要求是否以说明书为依据）
SUPPORT_CHECK_PROMPT = """请检查权利要求是否以说明书为依据（专利法第26条第4款）。

【权利要求】
{claims}

【说明书】
{description}

【规则要求】
{rule_requirement}

【法律依据】
{legal_basis}

判断原则：权利要求书中的每一项权利要求所要求保护的技术方案，在说明书中有充分、清楚的记载。

请逐条检查每个权利要求：
1. 权利要求中的每个技术特征是否在说明书中有记载？
2. 保护范围是否超出说明书公开的范围？
3. 说明书是否充分支持权利要求？

【输出格式】（严格 JSON）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "权利要求编号",
            "problem": "超出说明书范围的具体描述",
            "original_content": "权利要求中的表述（原文引用）",
            "suggested_content": "说明书中的对应记载或修改建议",
            "legal_reference": "专利法第26条第4款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 充分公开检查提示
SUFFICIENCY_CHECK_PROMPT = """请检查说明书是否充分公开（专利法第26条第3款）。

【说明书内容】
{description}

【权利要求】
{claims}

【技术领域】
{technical_field}

【规则要求】
{rule_requirement}

【法律依据】
{legal_basis}

判断标准：说明书应当对实用新型作出清楚、完整的说明，以所属技术领域的技术人员能够实现为准。

请审查：
1. 技术领域是否明确？
2. 背景技术是否客观描述现有技术？
3. 发明内容是否清楚完整（技术问题、技术方案、有益效果）？
4. 具体实施方式是否充分到本领域技术人员能够实现？
5. 是否公开了足够数量的实施例？

【输出格式】（严格 JSON）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "说明书具体章节",
            "problem": "不充分的具体描述",
            "original_content": "原文相关内容",
            "suggested_content": "需要补充的内容或修改建议",
            "legal_reference": "专利法第26条第3款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 新颖性评估提示
NOVELTY_CHECK_PROMPT = """请对以下专利权利要求进行新颖性评估（专利法第22条第2款）。

【待审查权利要求】
{claims}

【对比文件/现有技术】
{prior_art}

【规则要求】
{rule_requirement}

审查标准：新颖性要求申请日之前没有同样的发明或实用新型在国内外出版物上公开发表、在国内公开使用或者以其他方式为公众所知。

判断原则：
- 单独对比原则：每份对比文件单独与申请对比
- 相同披露原则：对比文件公开了权利要求的全部技术特征
- 直接地、毫无疑义原则：技术特征应明确公开，不能依赖推理

【输出格式】（严格 JSON）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "权利要求编号",
            "problem": "新颖性问题的具体分析",
            "original_content": "权利要求中与对比文件相同的技术特征",
            "suggested_content": "修改建议以克服新颖性问题",
            "legal_reference": "专利法第22条第2款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 创造性评估提示
INVENTIVENESS_CHECK_PROMPT = """请使用"三步法"对以下专利进行创造性评估（专利法第22条第3款）。

【权利要求】
{claims}

【现有技术/对比文件】
{prior_art}

【技术领域】
{technical_field}

【规则要求】
{rule_requirement}

三步法流程：
第一步：确定最接近的现有技术
第二步：确定区别技术特征和实际解决的技术问题
第三步：判断显而易见性

【输出格式】（严格 JSON）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "权利要求编号",
            "problem": "创造性问题的具体分析",
            "original_content": "区别技术特征的原文表述",
            "suggested_content": "修改建议以体现创造性",
            "legal_reference": "专利法第22条第3款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 单一性检查提示
UNITY_CHECK_PROMPT = """请判断以下专利申请是否符合单一性要求（专利法第31条第1款）。

【权利要求】
{claims}

【规则要求】
{rule_requirement}

判断标准：一件实用新型专利申请应当限于一项实用新型。属于一个总的发明构思的两项以上的实用新型，可以作为一件申请提出。

请分析：
1. 技术方案的数量
2. 各技术方案之间是否有相同/相应的特定技术特征
3. 单一性结论

【输出格式】（严格 JSON）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "权利要求编号",
            "problem": "单一性问题描述",
            "original_content": "相互独立的技术方案描述",
            "suggested_content": "修改建议",
            "legal_reference": "专利法第31条第1款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 保护客体检查提示
SUBJECT_MATTER_CHECK_PROMPT = """请判断以下技术方案是否属于实用新型专利保护客体（专利法第2条第3款）。

【技术方案】
{technical_solution}

【权利要求】
{claims}

实用新型定义：对产品的形状、构造或者其结合所提出的适于实用的新的技术方案。

符合保护客体：
- 产品的形状（如：手机的外形、玩具的造型）
- 产品的构造（如：机械结构、电子线路）
- 形状和构造的结合（如：可折叠的手机）

不符合保护客体：
- 纯方法（如：制造方法、处理方法）
- 材料配方（如：药品配方、涂料配方）
- 未经人工制造的物品（如：自然矿石、自然产物）
- 软件/算法（不涉及具体硬件构造）
- 气/液/粉状物质（不涉及具体形状构造）

【输出格式】（严格 JSON）
{{
    "passed": true/false,
    "issues": [
        {{
            "location": "权利要求或技术方案",
            "problem": "保护客体问题描述",
            "original_content": "涉及非保护客体的内容",
            "suggested_content": "修改建议",
            "legal_reference": "专利法第2条第3款",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

# 综合审查提示（用于发现规则库未覆盖的问题）
COMPREHENSIVE_REVIEW_PROMPT = """作为资深专利审查员，请对以下专利申请进行全面审查，发现规则库可能未覆盖的问题。

【专利信息】
标题：{title}
摘要：{abstract}
权利要求书：{claims}
说明书：{description}

请进行以下维度的审查：
1. 形式问题：编号、格式、引用、措辞
2. 保护客体：是否属于实用新型范围
3. 清楚性：权利要求是否清楚
4. 支持性：是否以说明书为依据
5. 充分公开：是否充分公开
6. 单一性：是否满足单一性要求
7. 新颖性/创造性（初步判断）
8. 其他可能存在的法律问题

【重要输出要求】
请使用清晰易读的格式输出分析结果，优先使用中文顿号、分号分隔问题列表。
不要输出JSON格式，使用以下格式：

## 审查结论：通过/不通过

### 一、发现的问题

#### 1. [问题类别] - [严重程度]
- **位置**: [具体位置]
- **问题**: [问题描述]
- **原文**: "[原文内容]"
- **建议**: [修改建议]
- **依据**: [法律依据]

#### 2. ...

### 二、总体评分
得分：XX/100分

### 三、总体评价
[详细说明专利的优点和不足]
"""

# 从规则内容获取检查提示的映射
RULE_TYPE_PROMPTS = {
    "clarity": CLARITY_CHECK_PROMPT,
    "support": SUPPORT_CHECK_PROMPT,
    "sufficiency": SUFFICIENCY_CHECK_PROMPT,
    "novelty": NOVELTY_CHECK_PROMPT,
    "inventiveness": INVENTIVENESS_CHECK_PROMPT,
    "unity": UNITY_CHECK_PROMPT,
    "subject_matter": SUBJECT_MATTER_CHECK_PROMPT,
    "comprehensive": COMPREHENSIVE_REVIEW_PROMPT,
}


def get_llm_prompt(rule_type: str, context: dict) -> str:
    """根据规则类型获取对应的 LLM 检查提示"""
    prompt_template = RULE_TYPE_PROMPTS.get(rule_type, COMPREHENSIVE_REVIEW_PROMPT)
    try:
        return prompt_template.format(**context)
    except KeyError as e:
        # 如果缺少必要参数，使用通用提示
        return COMPREHENSIVE_REVIEW_PROMPT.format(**context)
