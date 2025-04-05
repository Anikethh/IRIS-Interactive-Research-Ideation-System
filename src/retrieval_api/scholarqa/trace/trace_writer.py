from abc import ABC, abstractmethod
# from google.cloud import storage
import logging
import json
import os

logger = logging.getLogger(__name__)


class TraceWriter(ABC):
    @abstractmethod
    def write(self, trace_json, file_name: str) -> None:
        pass


class GCSWriter(TraceWriter):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name

    def write(self, trace_json, file_name: str) -> None:
        try:
            trace_json_str = json.dumps(trace_json.__dict__)
            storage_client = storage.Client()
            bucket = storage_client.bucket(self.bucket_name)
            blob = bucket.blob(f"{file_name}.json")
            blob.upload_from_string(trace_json_str)
            logger.info(f"Pushed event trace: {file_name}.json to GCS")
        except Exception as e:
            logger.info(f"Error pushing {file_name} to GCS: {e}")


class LocalWriter(TraceWriter):
    def __init__(self, local_dir: str):
        self.local_dir = local_dir
        if not os.path.exists(local_dir):
            logger.info(f"Creating local directory to record traces: {local_dir}")
            os.makedirs(local_dir)

    def write(self, trace_json, file_name: str) -> None:
        try:
            with open(f"{self.local_dir}/{file_name}.json", "w") as f:
                json.dump(trace_json.__dict__, f, indent=4)
            logger.info(f"Pushed event trace to local path: {self.local_dir}/{file_name}.json")
        except Exception as e:
            logger.info(f"Error pushing {file_name} to local directory: {e}")
