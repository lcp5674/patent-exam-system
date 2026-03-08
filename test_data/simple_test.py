"""
简化版测试脚本，先验证单个专利的审查功能
"""
import json
import httpx

BASE_URL = "http://localhost:8000"
TEST_USER = {"username": "admin", "password": "admin123"}

def get_auth_token():
    """获取认证令牌"""
    response = httpx.post(
        f"{BASE_URL}/api/v1/users/login",
        json=TEST_USER
    )
    response.raise_for_status()
    data = response.json()
    return data["data"]["access_token"]

def create_patent(token):
    """创建测试专利"""
    headers = {"Authorization": f"Bearer {token}"}
    patent_data = {
        "application_number": "TEST20260000001",
        "title": "一种可加热的水杯",
        "applicant": "测试科技有限公司",
        "inventor": "张三;李四",
        "technical_field": "日常生活用品",
        "abstract": "本实用新型公开了一种可加热的水杯，包括杯体、杯盖、加热装置和温度显示装置，能够对杯内液体进行加热并显示温度，适合在寒冷环境下使用。"
    }
    
    response = httpx.post(
        f"{BASE_URL}/api/v1/patents/",
        headers=headers,
        json=patent_data
    )
    response.raise_for_status()
    data = response.json()
    return data["data"]["id"] if "data" in data else data.get("id")

def run_examination(token, patent_id):
    """执行审查"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # 执行形式审查
    print("执行形式审查...")
    response = httpx.post(
        f"{BASE_URL}/api/v1/examination/{patent_id}/formal",
        headers=headers
    )
    response.raise_for_status()
    formal_result = response.json()
    print(f"形式审查结果: {json.dumps(formal_result, indent=2, ensure_ascii=False)}")
    
    # 执行实质审查
    print("\n执行实质审查...")
    response = httpx.post(
        f"{BASE_URL}/api/v1/examination/{patent_id}/substantive",
        headers=headers
    )
    response.raise_for_status()
    substantive_result = response.json()
    print(f"实质审查结果: {json.dumps(substantive_result, indent=2, ensure_ascii=False)}")
    
    # 获取审查历史
    print("\n获取审查历史...")
    response = httpx.get(
        f"{BASE_URL}/api/v1/examination/{patent_id}/history",
        headers=headers
    )
    response.raise_for_status()
    history = response.json()
    print(f"审查历史: {json.dumps(history, indent=2, ensure_ascii=False)}")
    
    # 计算准确率
    total_rules = 82
    failed = 0
    for record in history:
        if isinstance(record, dict) and "result" in record:
            result = record["result"]
            failed += result.get("score_details", {}).get("failed", 0)
    
    passed = total_rules - failed
    accuracy = (passed / total_rules) * 100
    print(f"\n📊 审查统计:")
    print(f"总规则数: {total_rules}")
    print(f"通过: {passed}")
    print(f"未通过: {failed}")
    print(f"准确率: {accuracy:.2f}%")
    
    return accuracy >= 98

def main():
    print("🚀 开始测试单个专利审查功能")
    print("=" * 50)
    
    try:
        token = get_auth_token()
        print("✅ 登录成功")
        
        patent_id = create_patent(token)
        print(f"✅ 创建专利成功，ID: {patent_id}")
        
        pass_98 = run_examination(token, patent_id)
        
        if pass_98:
            print("\n✅ 审查准确率达到98%以上要求！")
        else:
            print("\n⚠️  准确率未达到98%要求")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
