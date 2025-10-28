import os
from datetime import timedelta
from minio import Minio
from minio.error import S3Error

from dotenv import load_dotenv
load_dotenv()


class MinioUploader:
    def __init__(self, endpoint, access_key, secret_key, secure=False):
        self.minio_client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )

    def create_bucket_if_not_exists(self, bucket_name):
        try:
            if not self.minio_client.bucket_exists(bucket_name):
                self.minio_client.make_bucket(bucket_name)
            return True
        except S3Error as e:
            print(f"MinIO 错误: {e}")
            return False

    def upload_file(self, console_address, bucket_name, file_path, object_name, expires=timedelta(seconds=600)):
        try:
            # 检查并创建存储桶
            if not self.create_bucket_if_not_exists(bucket_name):
                return None, None

            # 上传文件
            self.minio_client.fput_object(
                bucket_name, object_name, file_path
            )

            minio_path = f"http://{console_address}/{bucket_name}/{object_name}"
            presigned_url = self.minio_client.presigned_get_object(
                bucket_name, object_name, expires=expires
            )
            return minio_path, presigned_url
        except S3Error as e:
            print(f"上传文件时发生 MinIO 错误: {e}")
            return None, None


if __name__ == "__main__":
    # 初始化 MinioUploader 类

    uploader = MinioUploader(
        os.getenv('MINIO_ENDPOINT'),
        access_key=os.getenv('MINIO_ACCESS_KEY'),
        secret_key=os.getenv('MINIO_SECRET_KEY'),
        secure=os.getenv('MINIO_SECURE', 'False').lower() == 'true'
    )

    console_address = "118.89.93.181:9001"
    bucket_name = "meeting-minutes"
    csv_file_path = 'alarm_records.csv'
    object_name = 'alarm_records.csv'

    minio_path, presigned_url = uploader.upload_file(console_address, bucket_name, csv_file_path, object_name)
    if minio_path and presigned_url:
        print(f"文件已上传，MinIO 路径: {minio_path}")
        print(f"预签名 URL: {presigned_url}")

