from locust import HttpUser, task, between
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UserBehavior(HttpUser):
    wait_time = between(5, 16)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "zh-CN,zh;q=0.9",
            "access-token": "tainsureAssistant_480f2f5b9fa9461d938c530104654505",
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0NTY5Yjc2LWYwODYtNDg0NC05OWJmLTk4MzA2Y2IwYmQ3MiIsImVtYWlsIjoiYWRtaW5AbWVldGluZy1zeXN0ZW0uY29tIiwicm9sZSI6ImFkbWluIiwidHlwZSI6ImFjY2VzcyIsImp0aSI6IjJlMDIxOTk4NTRiYzQwOTY4MTIyZWEwMjAxZDMzYTUwIiwiaWF0IjoxNzY0MjA2MTkyLCJuYmYiOjE3NjQyMDYxOTIsImV4cCI6MTc2NDIyMDU5MiwiaXNzIjoibWVldGluZy1hc3Npc3RhbnQiLCJhdWQiOiJtZWV0aW5nLWFzc2lzdGFudC1jbGllbnRzIn0.DM9zG7Fx9JV7R_Vr2Ts7hYqQDRdTMMTZd-boDXDCPGk"
        }

    def make_request(self, url, name):
        """通用的请求方法"""
        with self.client.get(
                url=url,
                headers=self.headers,
                verify=False,
                catch_response=True,
                name=name
        ) as response:

            print(f"\n=== {name} ===")
            print(f"URL: {url}")
            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    print(f"响应数据: {json_data}")

                    if "data" in json_data:
                        response.success()
                        return True
                    else:
                        response.failure("缺少data字段")
                        return False
                except Exception as e:
                    response.failure(f"JSON解析失败: {e}")
                    return False
            else:
                response.failure(f"状态码错误: {response.status_code}")
                print(f"响应文本: {response.text}")
                return False

    @task(2)
    def get_meeting_detail(self):
        """获取特定会议详情"""
        url = "https://159.75.114.74/api/meetings/5f4262c1-7742-42f7-ae98-778a605af981/user/"
        success = self.make_request(url, "获取会议详情")
        if success:
            print("✅ 会议详情获取成功")

    @task(1)
    def get_user_meetings(self):
        """获取用户的所有会议"""
        url = "https://159.75.114.74/api/meetings/user/"
        success = self.make_request(url, "获取用户会议列表")
        if success:
            print("✅ 用户会议列表获取成功")

