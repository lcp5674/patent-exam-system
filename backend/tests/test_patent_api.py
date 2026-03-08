"""专利管理API测试"""
import pytest
import json
from fastapi.testclient import TestClient
from app.core.auth import create_access_token


class TestPatentListAPI:
    """测试专利列表查询API"""

    def test_get_patent_list_unauthorized(self, test_client):
        """未授权访问应该失败"""
        response = test_client.get("/api/v1/patents")
        assert response.status_code == 401

    def test_get_patent_list_authorized(self, test_client, test_user_token):
        """授权用户应该能访问专利列表"""
        response = test_client.get(
            "/api/v1/patents",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "code" in data
        assert data["code"] == 200
        assert "patents" in data["data"]

    def test_patent_list_pagination(self, test_client, test_user_token):
        """测试分页功能"""
        response = test_client.get(
            "/api/v1/patents?page=2&page_size=10",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page"] == 2
        assert data["data"]["page_size"] == 10

    def test_patent_list_filtering(self, test_client, test_user_token):
        """测试过滤功能"""
        # 按申请号过滤
        response = test_client.get(
            "/api/v1/patents?application_no=CN2024",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200

    def test_patent_list_sorting(self, test_client, test_user_token):
        """测试排序功能"""
        response = test_client.get(
            "/api/v1/patents?sort_by=created_at&sort_order=desc",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200


class TestPatentDetailAPI:
    """测试专利详情查询API"""

    def test_get_patent_detail(self, test_client, test_user_token, sample_patent):
        """获取专利详情"""
        patent_id = sample_patent["application_number"]
        response = test_client.get(
            f"/api/v1/patents/{patent_id}",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "patent" in data["data"]
        assert data["data"]["patent"]["application_number"] == patent_id

    def test_get_nonexistent_patent(self, test_client, test_user_token):
        """获取不存在的应该返回404"""
        response = test_client.get(
            "/api/v1/patents/NONEXISTENT",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404


class TestPatentCreateAPI:
    """测试专利创建API"""

    def test_create_patent(self, test_client, test_examiner_token, sample_patent):
        """创建专利"""
        response = test_client.post(
            "/api/v1/patents",
            json=sample_patent,
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["code"] in [200, 201]
        assert "patent" in data["data"]

    def test_create_patent_unauthorized(self, test_client, sample_patent):
        """未授权创建应该失败"""
        response = test_client.post(
            "/api/v1/patents",
            json=sample_patent
        )
        assert response.status_code == 401

    def test_create_patent_invalid_data(self, test_client, test_examiner_token):
        """无效数据应该返回422"""
        invalid_patent = {
            "title": "",  # 空标题
            "applicant": "Test",
            # 缺少必填字段
        }
        response = test_client.post(
            "/api/v1/patents",
            json=invalid_patent,
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        assert response.status_code == 422


class TestPatentUpdateAPI:
    """测试专利更新API"""

    def test_update_patent(self, test_client, test_examiner_token, sample_patent):
        """更新专利信息"""
        patent_id = sample_patent["application_number"]
        update_data = {"title": "更新后的专利标题"}

        response = test_client.put(
            f"/api/v1/patents/{patent_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        assert response.status_code == 200


class TestPatentDeleteAPI:
    """测试专利删除API"""

    def test_delete_patent(self, test_client, test_examiner_token, sample_patent):
        """软删除专利"""
        patent_id = sample_patent["application_number"]

        response = test_client.delete(
            f"/api/v1/patents/{patent_id}",
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        assert response.status_code == 200

        # 验证已被软删除
        response = test_client.get(
            f"/api/v1/patents/{patent_id}",
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        # 被软删除的项目应该不可见或标记为已删除


class TestPatentAnalysisAPI:
    """测试专利审查分析API"""

    def test_patent_analysis(self, test_client, test_examiner_token, sample_patent):
        """提交专利进行AI分析"""
        patent_id = sample_patent["application_number"]

        # 请求AI分析
        response = test_client.post(
            f"/api/v1/patents/{patent_id}/analysis",
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "analysis_id" in data["data"]

        # 检查分析结果
        analysis_id = data["data"]["analysis_id"]
        response = test_client.get(
            f"/api/v1/patents/{patent_id}/analysis/{analysis_id}",
            headers={"Authorization": f"Bearer {test_examiner_token}"}
        )
        assert response.status_code == 200
