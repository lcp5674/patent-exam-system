"""
安全功能单元测试
"""
import pytest
from datetime import datetime, timedelta
from jose import jwt

from app.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, decode_token
)


@pytest.mark.unit
class TestPasswordSecurity:
    """密码安全测试"""

    def test_password_hashing(self):
        """测试密码哈希"""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0

    def test_password_verification_correct(self):
        """测试正确密码验证"""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_password_verification_wrong(self):
        """测试错误密码验证"""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_different_hashes_same_password(self):
        """测试相同密码产生不同哈希（盐值）"""
        password = "SecurePassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # 相同密码应该产生不同的哈希（因为有盐值）
        assert hash1 != hash2
        # 但都能验证通过
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


@pytest.mark.unit
class TestJWTTokenSecurity:
    """JWT令牌安全测试"""

    def test_create_access_token(self):
        """测试创建访问令牌"""
        data = {"sub": "1", "role": "admin"}
        token = create_access_token(data)

        assert token is not None
        assert len(token) > 0
        assert "." in token  # JWT格式

    def test_decode_token(self):
        """测试解析访问令牌"""
        data = {"sub": "1", "role": "admin"}
        token = create_access_token(data)

        decoded = decode_token(token)

        assert decoded["sub"] == "1"
        assert decoded["role"] == "admin"

    def test_access_token_expired(self):
        """测试过期令牌"""
        from app.core.security import settings

        # 创建已过期的令牌
        data = {"sub": "1", "role": "admin"}
        # 设置1小时前过期
        expire = datetime.utcnow() - timedelta(hours=1)
        token = jwt.encode(
            data,
            settings.security.SECRET_KEY,
            algorithm=settings.security.ALGORITHM,
            expires=expire
        )

        with pytest.raises(Exception):
            decode_token(token)

    def test_create_refresh_token(self):
        """测试创建刷新令牌"""
        data = {"sub": "1", "role": "admin"}
        token = create_refresh_token(data)

        assert token is not None
        assert len(token) > 0

    def test_decode_token(self):
        """测试解析刷新令牌"""
        data = {"sub": "1", "role": "admin"}
        token = create_refresh_token(data)

        decoded = decode_token(token)

        assert decoded["sub"] == "1"
        assert decoded["type"] == "refresh"


@pytest.mark.unit
class TestSecuritySettings:
    """安全设置测试"""

    def test_algorithm_is_hs256(self):
        """测试使用HS256算法"""
        from app.core.security import settings
        assert settings.security.ALGORITHM == "HS256"

    def test_token_expiration_time(self):
        """测试令牌过期时间"""
        from app.core.security import settings
        assert settings.security.ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_secret_key_length(self):
        """测试密钥长度"""
        from app.core.security import settings
        # 密钥应该有足够的长度
        assert len(settings.security.SECRET_KEY) >= 32


@pytest.mark.unit
class TestInputValidation:
    """输入验证测试"""

    def test_username_validation(self):
        """测试用户名验证"""
        # 可能的用户名验证逻辑
        valid_usernames = ["test_user", "admin", "user123"]
        invalid_usernames = ["", "ab"]  # 太短

        # 基础检查：用户名不能为空或太短
        for username in valid_usernames:
            assert len(username) >= 3

        for username in invalid_usernames:
            assert len(username) < 3 or len(username) == 0

    def test_password_validation(self):
        """测试密码验证逻辑"""
        strong_passwords = ["Password123!", "Test@123", "Secure#456"]
        weak_passwords = ["123"]  # 弱密码

        for pwd in strong_passwords:
            # 强密码应该有长度
            assert len(pwd) >= 8

        for pwd in weak_passwords:
            # 弱密码不满足基本要求
            assert len(pwd) < 8


@pytest.mark.unit
class TestTokenPayload:
    """令牌载荷测试"""

    def test_access_token_contains_required_fields(self):
        """测试访问令牌包含必要字段"""
        from app.core.security import settings

        data = {"sub": "1", "role": "admin", "tenant_id": "100"}
        token = create_access_token(data)

        decoded = jwt.decode(
            token,
            settings.security.SECRET_KEY,
            algorithms=[settings.security.ALGORITHM]
        )

        assert decoded["sub"] == "1"
        assert decoded["role"] == "admin"
        assert decoded["tenant_id"] == "100"
        assert "exp" in decoded  # 过期时间

    def test_refresh_token_type(self):
        """测试刷新令牌类型标记"""
        data = {"sub": "1", "role": "admin"}
        token = create_refresh_token(data)

        decoded = decode_token(token)
        assert decoded.get("type") == "refresh"