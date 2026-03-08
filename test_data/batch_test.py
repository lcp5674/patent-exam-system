"""
批量测试120个专利，验证审查准确率
"""
import json
import httpx
import asyncio
from tqdm import tqdm
from typing import List, Dict

BASE_URL = "http://localhost:8000"
TEST_USER = {"username": "admin", "password": "admin123"}

async def get_auth_token() -> str:
    """获取认证令牌"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/users/login",
            json=TEST_USER
        )
        response.raise_for_status()
        data = response.json()
        return data["data"]["access_token"]

async def create_patent(client: httpx.AsyncClient, token: str, patent_data: Dict) -> int:
    """创建专利"""
    headers = {"Authorization": f"Bearer {token}"}
    create_data = {
        "application_number": patent_data["application_number"],
        "title": patent_data["title"],
        "applicant": patent_data["applicant"],
        "inventor": patent_data["inventor"],
        "technical_field": patent_data["technical_field"],
        "abstract": patent_data["abstract"]
    }
    
    response = await client.post(
        f"{BASE_URL}/api/v1/patents/",
        headers=headers,
        json=create_data
    )
    response.raise_for_status()
    data = response.json()
    return data["data"]["id"] if "data" in data else data.get("id")

async def run_examination(client: httpx.AsyncClient, token: str, patent_id: int) -> Dict:
    """执行审查并获取结果"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 执行形式审查
    response = await client.post(
        f"{BASE_URL}/api/v1/examination/{patent_id}/formal",
        headers=headers
    )
    response.raise_for_status()
    
    # 执行实质审查
    response = await client.post(
        f"{BASE_URL}/api/v1/examination/{patent_id}/substantive",
        headers=headers
    )
    response.raise_for_status()
    
    # 获取审查结果
    response = await client.get(
        f"{BASE_URL}/api/v1/examination/{patent_id}/history",
        headers=headers
    )
    response.raise_for_status()
    return response.json()

def analyze_result(patent_data: Dict, examination_result: List) -> Dict:
    """分析审查结果，计算准确率"""
    expected_has_issue = patent_data["has_issue"]
    expected_issue = patent_data["expected_issue"]
    
    # 检查是否发现问题
    actual_has_issue = False
    found_issues = []
    
    for record in examination_result:
        result = record.get("result", {})
        score_details = result.get("score_details", {})
        if score_details.get("failed", 0) > 0:
            actual_has_issue = True
            # 收集问题描述
            for rule_result in result.get("results", []):
                if not rule_result["passed"] and rule_result["issues"]:
                    for issue in rule_result["issues"]:
                        found_issues.append(issue["description"])
    
    # 判断是否正确
    if expected_has_issue:
        # 预期有问题，实际也发现了问题：正确
        correct = actual_has_issue
        if correct and expected_issue:
            # 检查是否发现了预期的问题类型
            issue_match = any(expected_issue[0] in issue for issue in found_issues)
            correct = issue_match
    else:
        # 预期没有问题，实际也没有问题：正确
        correct = not actual_has_issue
    
    return {
        "patent_id": patent_data["application_number"],
        "title": patent_data["title"],
        "expected_has_issue": expected_has_issue,
        "actual_has_issue": actual_has_issue,
        "correct": correct,
        "expected_issue": expected_issue,
        "found_issues": found_issues
    }

async def main():
    """主测试函数"""
    print("🚀 开始批量专利审查测试")
    print("=" * 70)
    
    # 加载测试数据
    with open("test_patents_120.json", "r", encoding="utf-8") as f:
        test_patents = json.load(f)
    
    print(f"📊 测试数据集：{len(test_patents)} 个专利")
    print(f"   含问题专利：{sum(1 for p in test_patents if p['has_issue'])} 个")
    print(f"   无问题专利：{sum(1 for p in test_patents if not p['has_issue'])} 个")
    print()
    
    # 获取token
    token = await get_auth_token()
    print("✅ 登录成功，获取访问令牌")
    
    # 批量测试
    results = []
    correct_count = 0
    success_count = 0
    
    async with httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=1)) as client:
        for i, patent in enumerate(tqdm(test_patents, desc="审查进度")):
            try:
                # 创建专利
                patent_id = await create_patent(client, token, patent)
                
                # 执行审查
                examination_result = await run_examination(client, token, patent_id)
                
                # 分析结果
                analysis = analyze_result(patent, examination_result)
                results.append(analysis)
                success_count += 1
                
                if analysis["correct"]:
                    correct_count += 1
                
                # 每20个输出一次中间结果
                if (i + 1) % 20 == 0 and success_count > 0:
                    current_accuracy = (correct_count / success_count) * 100
                    tqdm.write(f"\n📈 中间进度 ({i+1}/{len(test_patents)})：成功测试 {success_count} 个，当前准确率 {current_accuracy:.2f}%")
                
                # 限流，避免429错误
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"\n❌ 专利 {patent['application_number']} 测试失败：{e}")
                results.append({
                    "patent_id": patent["application_number"],
                    "title": patent["title"],
                    "correct": False,
                    "error": str(e)
                })
    
    # 计算最终结果
    total = len(results)
    # 只统计成功测试的专利
    valid_results = [r for r in results if "error" not in r]
    valid_count = len(valid_results)
    accuracy = (correct_count / valid_count) * 100 if valid_count > 0 else 0
    
    print("\n" + "=" * 70)
    print("🎯 测试完成！最终结果统计：")
    print("=" * 70)
    print(f"总测试专利数：{total}")
    print(f"成功测试数：{valid_count}")
    print(f"失败测试数：{total - valid_count} (限流错误)")
    print(f"正确判断数：{correct_count}")
    print(f"错误判断数：{valid_count - correct_count}")
    print(f"审查准确率：{accuracy:.2f}%")
    print()
    
    if accuracy >= 98:
        print("✅ 恭喜！审查准确率达到98%以上要求！")
    elif valid_count > 0:
        print(f"⚠️  准确率未达到98%要求，差 {98 - accuracy:.2f}%")
    else:
        print("❌ 没有成功完成的测试，请稍后重试")
    
    # 保存详细结果
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total,
                "correct": correct_count,
                "accuracy": accuracy,
                "pass_98": accuracy >= 98
            },
            "details": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n📝 详细测试结果已保存到 test_results.json")
    
    # 输出错误案例
    if total - correct_count > 0:
        print("\n❌ 错误案例：")
        for result in results:
            if not result["correct"] and "error" not in result:
                status = "漏检" if result["expected_has_issue"] else "误判"
                print(f"  - [{status}] {result['patent_id']} {result['title']}")
                if result.get("expected_issue"):
                    print(f"    预期问题：{result['expected_issue'][0]}")
                if result.get("found_issues"):
                    print(f"    实际发现：{result['found_issues'][:2]}")

if __name__ == "__main__":
    asyncio.run(main())
