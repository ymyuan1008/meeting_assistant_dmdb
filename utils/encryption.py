import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.fernet import Fernet
import base64
from typing import Tuple


class RSAEncryption:
    """RSA加密工具类"""
    
    def __init__(self):
        # 生成RSA密钥对
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        self.public_key = self.private_key.public_key()
    
    def get_public_key_pem(self) -> str:
        """获取PEM格式的公钥"""
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')
    
    def encrypt(self, plaintext: str) -> str:
        """使用公钥加密"""
        plaintext_bytes = plaintext.encode('utf-8')
        ciphertext = self.public_key.encrypt(
            plaintext_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(ciphertext).decode('utf-8')
    
    def decrypt(self, ciphertext: str) -> str:
        """使用私钥解密"""
        ciphertext_bytes = base64.b64decode(ciphertext.encode('utf-8'))
        plaintext = self.private_key.decrypt(
            ciphertext_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext.decode('utf-8')


# 创建全局加密实例
rsa_encryption = RSAEncryption()