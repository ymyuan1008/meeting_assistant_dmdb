import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
import base64
from loguru import logger

# 定义密钥文件路径（建议放在项目根目录或 config 目录）
PRIVATE_KEY_PATH = Path("keys/private_key.pem")
PUBLIC_KEY_PATH = Path("keys/public_key.pem")


class RSAEncryption:
    """RSA加密工具类（使用固定密钥对）"""
    
    def __init__(self):
        # 确保 keys 目录存在
        PRIVATE_KEY_PATH.parent.mkdir(exist_ok=True)

        if PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
            # 从文件加载密钥
            logger.info("正在从文件加载 RSA 密钥对...")
            self._load_keys()
        else:
            # 生成新密钥对并保存到文件
            logger.warning("未找到 RSA 密钥文件，正在生成新的密钥对...")
            self._generate_and_save_keys()

    def _generate_and_save_keys(self):
        """生成密钥对并保存到文件"""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()

        # 保存私钥（无密码）
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # 保存公钥
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

        logger.success(f"RSA 密钥对已保存至: {PRIVATE_KEY_PATH.parent}")

    def _load_keys(self):
        """从文件加载密钥对"""
        with open(PRIVATE_KEY_PATH, "rb") as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None  # 无密码
            )

        with open(PUBLIC_KEY_PATH, "rb") as f:
            self.public_key = serialization.load_pem_public_key(f.read())

    def get_public_key_pem(self) -> str:
        """获取PEM格式的公钥（用于前端）"""
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')

    def encrypt(self, plaintext: str) -> str:
        """使用公钥加密（通常前端做，这里仅用于测试）"""
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = self.public_key.encrypt(
            plaintext_bytes,
            padding.PKCS1v15()
        )
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """使用私钥解密（后端使用）"""
        try:
            ciphertext_bytes = base64.b64decode(ciphertext.encode('utf-8'))
            plaintext_bytes = self.private_key.decrypt(
                ciphertext_bytes,
                padding.PKCS1v15()
            )
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"RSA解密失败: {e}")
            raise ValueError("密码解密失败，请检查密钥或加密方式是否匹配") from e


# 创建全局加密实例
rsa_encryption = RSAEncryption()