from aiobotocore.session import get_session
from aiobotocore.config import AioConfig
from io import BytesIO
from typing import List, Dict, Optional
import uuid
import logging
import aiofiles
import os
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self, config):
        self.config = config
        self.session = get_session()

        # Проверка конфигурации
        required_params = ['aws_access_key_id', 'aws_secret_access_key', 's3_endpoint_url', 's3_bucket']
        for param in required_params:
            if not hasattr(self.config, param) or not getattr(self.config, param):
                logger.error(f"Missing required S3 configuration parameter: {param}")
                raise ValueError(f"Missing required S3 configuration parameter: {param}")

        # Конфигурация клиента
        self.client_config = {
            "aws_access_key_id": self.config.aws_access_key_id,
            "aws_secret_access_key": self.config.aws_secret_access_key,
            "endpoint_url": self.config.s3_endpoint_url,
            "region_name": getattr(self.config, 's3_region', 'ru-central1'),  # Дефолтное значение
            "config": AioConfig(
                s3={'addressing_style': 'path'},
                signature_version='s3v4'
            )
        }

        # Используем значение из конфигурации
        self.bucket = 'beatrice'
        self.local_storage_path = getattr(self.config, 'local_storage_path', './uploads')

        # Создаем директорию для локального сохранения
        os.makedirs(self.local_storage_path, exist_ok=True)

    async def upload_photo(self, file_data: BytesIO, user_id: int) -> Optional[str]:
        """
        Загружает фото в S3 хранилище и возвращает URL для доступа к нему

        Args:
            file_data: BytesIO объект с данными файла
            user_id: ID пользователя

        Returns:
            Optional[str]: URL загруженного файла или None в случае ошибки
        """
        try:
            # Проверка размера файла
            file_data.seek(0)  # Перемещаем указатель в начало
            file_bytes = file_data.getvalue()
            file_size = len(file_bytes)

            if file_size > 5 * 1024 * 1024:  # 5 МБ
                logger.warning(f"File too large: {file_size} bytes for user {user_id}")
                return None

            # Генерация уникального имени файла
            file_uuid = str(uuid.uuid4())
            file_key = f"{user_id}/{file_uuid}.jpg"
            local_path = os.path.join(self.local_storage_path, f"{user_id}_{file_uuid}.jpg")

            try:
                # Сохраняем файл локально
                async with aiofiles.open(local_path, 'wb') as f:
                    await f.write(file_bytes)
                logger.info(f"File saved locally: {local_path}")
            except Exception as local_error:
                logger.error(f"Local save failed: {str(local_error)}")
                # Продолжаем попытку загрузки в S3 даже если локальное сохранение не удалось

            # Загрузка в S3
            async with self.session.create_client("s3", **self.client_config) as client:
                # Проверка бакета
                try:
                    await client.head_bucket(Bucket=self.bucket)
                    logger.debug(f"Bucket {self.bucket} exists and is accessible")
                except Exception as bucket_error:
                    logger.error(f"Bucket check failed: {str(bucket_error)}")
                    return None

                # Загрузка содержимого файла
                try:
                    await client.put_object(
                        Bucket=self.bucket,
                        Key=file_key,
                        Body=file_bytes,
                        ContentType="image/jpeg"
                    )
                    logger.info(f"File uploaded to S3: {file_key}")
                except Exception as upload_error:
                    logger.error(f"S3 upload failed: {str(upload_error)}")
                    return None

                # Формирование URL
                base_url = self.config.s3_endpoint_url.rstrip('/')
                file_url = f"{base_url}/{self.bucket}/{file_key}"
                logger.info(f"File URL: {file_url}")

                return file_url

        except Exception as e:
            logger.error(f"Error processing file for user {user_id}: {str(e)}")
            return None

    async def delete_user_photos(self, user_id: int) -> bool:
        """
        Удаляет все файлы пользователя из S3 и локального хранилища

        Args:
            user_id: Telegram ID пользователя

        Returns:
            bool: True если удаление успешно, False в случае ошибки
        """
        try:
            # Формируем префикс для S3
            s3_prefix = f"{user_id}/"

            # Удаление из S3
            async with self.session.create_client("s3", **self.client_config) as client:
                # Получаем список всех объектов пользователя
                list_response = await client.list_objects_v2(
                    Bucket=self.bucket,
                    Prefix=s3_prefix
                )

                if 'Contents' in list_response:
                    # Формируем список ключей для удаления
                    objects_to_delete = [
                        {'Key': obj['Key']}
                        for obj in list_response['Contents']
                    ]

                    # Пакетное удаление объектов
                    await client.delete_objects(
                        Bucket=self.bucket,
                        Delete={'Objects': objects_to_delete}
                    )
                    logger.info(f"Deleted {len(objects_to_delete)} files from S3 for user {user_id}")

            return True

        except Exception as e:
            logger.error(f"Error deleting files for user {user_id}: {str(e)}")
            return False

    async def download_photos_by_urls(self, urls: list[str]) -> list[str]:
        """
        Скачивает файлы из S3 по URL и возвращает локальные пути
        Args:
            urls: Список полных URL файлов в S3

        Returns:
            list[str]: Список абсолютных путей к скачанным файлам
        """
        local_paths = []

        async with self.session.create_client("s3", **self.client_config) as client:
            for url in urls:
                try:
                    # Парсим URL и извлекаем ключ
                    parsed = urlparse(url)
                    key = parsed.path.lstrip('/').replace(f"{self.bucket}/", "", 1)

                    # Формируем локальный путь
                    local_path = os.path.join(
                        self.local_storage_path,
                        key.replace("/", "_")  # user_id/filename.jpg -> user_id_filename.jpg
                    )

                    # Скачиваем файл
                    success = await self._download_file(client, key, local_path)

                    if success:
                        local_paths.append(os.path.abspath(local_path))

                except Exception as e:
                    logger.error(f"Failed to process {url}: {str(e)}")

        return local_paths

    async def _download_file(self, client, s3_key: str, local_path: str) -> bool:
        """Скачивает один файл из S3"""
        try:
            # Создаем директорию если нужно
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Скачиваем файл
            response = await client.get_object(
                Bucket=self.bucket,
                Key=s3_key
            )

            async with response["Body"] as stream:
                content = await stream.read()

                async with aiofiles.open(local_path, "wb") as f:
                    await f.write(content)

            logger.info(f"Downloaded {s3_key} -> {local_path}")
            return True

        except Exception as e:
            logger.error(f"Download failed for {s3_key}: {str(e)}")
            return False