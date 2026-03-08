"""
生成100+模拟专利测试数据集
"""
import json
import random
from faker import Faker
from datetime import datetime

fake = Faker('zh_CN')

# 专利技术领域列表
TECH_FIELDS = [
    "电子信息", "人工智能", "生物医药", "机械制造", "化工材料",
    "新能源", "航空航天", "农业技术", "交通运输", "环境保护",
    "半导体", "通信技术", "计算机软件", "医疗器械", "食品加工"
]

# 专利问题类型
ISSUE_TYPES = [
    None,  # 无问题
    ["缺少附图", "实用新型专利必须有说明书附图"],
    ["权利要求不清晰", "权利要求中含有模糊用语"],
    ["说明书公开不充分", "所属技术领域人员无法实现"],
    ["缺少必要技术特征", "独立权利要求缺少必要技术特征"],
    ["摘要过长", "摘要超过300字"],
    ["保护客体问题", "不属于实用新型保护客体"],
    ["单一性问题", "不属于一个总的发明构思"]
]

def generate_patent(index: int) -> dict:
    """生成单个测试专利"""
    has_issue = random.random() < 0.3  # 30%的专利有问题
    issue = random.choice(ISSUE_TYPES) if has_issue else None
    
    tech_field = random.choice(TECH_FIELDS)
    invention_name = fake.sentence(nb_words=6, variable_nb_words=True).replace("。", "")
    
    # 生成权利要求
    claims = []
    for i in range(random.randint(1, 5)):
        if i == 0:
            claim_text = f"1. 一种{invention_name}，其特征在于，包括：{fake.sentence(nb_words=10)}"
        else:
            claim_text = f"{i+1}. 根据权利要求{i}所述的{invention_name}，其特征在于，{fake.sentence(nb_words=8)}"
        claims.append(claim_text)
    
    # 生成说明书
    description = {
        "技术领域": f"本发明涉及{tech_field}技术领域，具体涉及一种{invention_name}。",
        "背景技术": fake.paragraph(nb_sentences=3),
        "发明内容": fake.paragraph(nb_sentences=4),
        "具体实施方式": fake.paragraph(nb_sentences=5)
    }
    
    # 如果有附图问题，移除附图说明
    if issue and "缺少附图" in issue[0]:
        description.pop("附图说明", None)
    else:
        description["附图说明"] = "图1是本发明的结构示意图。"
    
    patent = {
        "application_number": f"CN{datetime.now().year}{random.randint(1000000, 9999999)}.{random.randint(1, 9)}",
        "title": invention_name,
        "applicant": fake.company(),
        "inventor": ";".join([fake.name() for _ in range(random.randint(1, 3))]),
        "technical_field": tech_field,
        "abstract": fake.paragraph(nb_sentences=2) if not (issue and "摘要过长" in issue[0]) else fake.paragraph(nb_sentences=10),
        "claims": claims,
        "description": description,
        "has_issue": issue is not None,
        "expected_issue": issue
    }
    
    return patent

def main():
    """生成120个测试专利"""
    patents = []
    for i in range(120):
        patent = generate_patent(i)
        patents.append(patent)
        if (i + 1) % 20 == 0:
            print(f"已生成 {i+1}/120 个专利")
    
    # 保存到文件
    with open("test_patents_120.json", "w", encoding="utf-8") as f:
        json.dump(patents, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 成功生成120个测试专利，保存到 test_patents_120.json")
    print(f"   含问题专利数量：{sum(1 for p in patents if p['has_issue'])}")
    print(f"   无问题专利数量：{sum(1 for p in patents if not p['has_issue'])}")

if __name__ == "__main__":
    main()
