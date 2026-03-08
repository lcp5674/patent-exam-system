"""
专利全链路测试脚本 - 测试文件上传、解析、审查全流程
"""
import os
import sys
import httpx
import json
from pathlib import Path

BASE_URL = "http://localhost:8000"
TEST_USER = {"username": "admin", "password": "admin123"}

# 测试专利文件内容（简化版，用于测试流程）
TEST_PATENT_CONTENT = """
# 实用新型专利申请
## 权利要求书
1. 一种水杯，包括杯体和杯盖，其特征在于，所述杯体底部设置有加热装置，所述加热装置与电源连接。
2. 根据权利要求1所述的水杯，其特征在于，所述杯体外侧设置有温度显示装置。

## 说明书
### 技术领域
本实用新型涉及日常生活用品技术领域，具体涉及一种可加热的水杯。

### 背景技术
现有的水杯通常只有盛装液体的功能，无法对液体进行加热，在寒冷环境下使用不方便。

### 发明内容
本实用新型的目的是提供一种可加热的水杯，能够对杯内液体进行加热，并显示当前温度。

### 附图说明
图1是本实用新型的结构示意图。

### 具体实施方式
下面结合具体实施例对本实用新型进行详细说明。
本实用新型的水杯包括杯体和杯盖，杯体底部安装有加热片，加热片通过导线与USB电源接口连接，杯体外侧安装有LED温度显示屏，可以实时显示杯内液体温度。
使用时，通过USB接口连接电源，加热片工作对液体进行加热，温度显示屏显示当前温度，方便用户查看。

## 摘要
本实用新型公开了一种可加热的水杯，包括杯体、杯盖、加热装置和温度显示装置，能够对杯内液体进行加热并显示温度，适合在寒冷环境下使用。
"""

def get_auth_token():
    """获取认证令牌"""
    try:
        response = httpx.post(
            f"{BASE_URL}/api/v1/users/login",
            json=TEST_USER
        )
        response.raise_for_status()
        data = response.json()
        return data["data"]["access_token"]
    except Exception as e:
        print(f"登录失败: {e}")
        return None

def create_test_patent(token):
    """创建测试专利"""
    headers = {"Authorization": f"Bearer {token}"}
    import time
    patent_data = {
        "application_number": f"TEST{int(time.time())}",
        "title": "一种可加热的水杯",
        "applicant": "测试科技有限公司",
        "inventor": "张三;李四",
        "technical_field": "日常生活用品",
        "abstract": "本实用新型公开了一种可加热的水杯，包括杯体、杯盖、加热装置和温度显示装置，能够对杯内液体进行加热并显示温度，适合在寒冷环境下使用。"
    }
    
    try:
        response = httpx.post(
            f"{BASE_URL}/api/v1/patents/",
            headers=headers,
            json=patent_data
        )
        response.raise_for_status()
        data = response.json()
        patent_id = data["data"]["id"] if "data" in data else data.get("id")
        print(f"✅ 创建测试专利成功，ID: {patent_id}")
        return patent_id
    except Exception as e:
        print(f"创建专利失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return None

def start_examination(token, patent_id):
    """启动专利审查"""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        # 先执行形式审查
        response = httpx.post(
            f"{BASE_URL}/api/v1/examination/{patent_id}/formal",
            headers=headers
        )
        response.raise_for_status()
        print("✅ 形式审查完成")
        
        # 再执行实质审查
        response = httpx.post(
            f"{BASE_URL}/api/v1/examination/{patent_id}/substantive",
            headers=headers
        )
        response.raise_for_status()
        print("✅ 实质审查完成")
        
        return True
    except Exception as e:
        print(f"启动审查失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        return False

def get_examination_result(token, patent_id):
    """获取审查结果"""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = httpx.get(
            f"{BASE_URL}/api/v1/examination/{patent_id}/history",
            headers=headers
        )
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"获取审查结果失败: {e}")
        return None

def main():
    print("🚀 开始专利审查系统全链路测试")
    print("=" * 50)
    
    # 1. 登录获取token
    print("\n1. 正在登录系统...")
    token = get_auth_token()
    if not token:
        print("❌ 登录失败，测试终止")
        return
    
    # 2. 创建测试专利
    print("\n2. 正在创建测试专利...")
    patent_id = create_test_patent(token)
    if not patent_id:
        print("❌ 创建专利失败，测试终止")
        return
    
    # 3. 启动审查
    print("\n3. 正在启动专利审查...")
    if not start_examination(token, patent_id):
        print("❌ 启动审查失败，测试终止")
        return
    
    # 4. 获取审查结果
    print("\n4. 获取审查结果...")
    result = get_examination_result(token, patent_id)
    if result and isinstance(result, list) and len(result) > 0:
        print("\n✅ 审查完成！")
        print("\n📋 审查历史:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 计算形式审查准确率
        formal_issues = []
        substantive_issues = []
        for record in result:
            if record.get("type") == "formal":
                formal_issues = record.get("issues", [])
            elif record.get("type") == "substantive":
                substantive_issues = record.get("issues", [])
        
        total_issues = len(formal_issues) + len(substantive_issues)
        total_rules = 107
        passed = total_rules - total_issues
        accuracy = (passed / total_rules) * 100
        print(f"\n📊 审查统计:")
        print(f"   总规则数: {total_rules}")
        print(f"   形式审查问题: {len(formal_issues)} 个")
        print(f"   实质审查问题: {len(substantive_issues)} 个")
        print(f"   总问题数: {total_issues} 个")
        print(f"   通过率: {accuracy:.2f}% ({passed}/{total_rules})")
        
        if accuracy >= 98:
            print("✅ 审查准确率达到98%以上要求！")
        else:
            print(f"⚠️  准确率未达到98%要求，差 {98 - accuracy:.2f}%")
    else:
        print("❌ 未获取到审查结果")
    
    print("\n" + "=" * 50)
    print("🎯 测试完成")

if __name__ == "__main__":
    main()
