import requests
import json
import base64

from utils.encryption import rsa_encryption


encrypt_text = "Admin123456"
encrypted_text = rsa_encryption.encrypt(encrypt_text)
print("加密后的密码:", encrypted_text)

decrypted_text = rsa_encryption.decrypt(encrypted_text)
print("解密密后的明文:", decrypted_text)

# 检查密文是否需要Base64编码
# 如果加密结果是bytes类型，转换为Base64字符串
if isinstance(encrypted_text, bytes):
    encrypted_text = base64.b64encode(encrypted_text).decode('utf-8')
    print("Base64编码后的密文:", encrypted_text)

# 发送POST请求 - JSON数据
url = "https://159.75.159.163/api/auth/login"
json_data = {
    "username": "admin",
    "password": encrypted_text
}

headers = {
    "Content-Type": "application/json"
}

print("发送的请求数据:", json.dumps(json_data, indent=2, ensure_ascii=False))

response = requests.post(url, json=json_data, headers=headers, verify=False)

print("响应状态码:", response.status_code)
print("响应头:", dict(response.headers))
print("响应数据:", response.text)

# 断言响应状态码为200
assert response.status_code == 200, f"Expected 200, but got {response.status_code}. Response: {response.text}"

# 打印响应数据
print("解析后的JSON响应:", response.json())