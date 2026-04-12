import os
from pathlib import Path

from google.oauth2 import service_account
from langchain_google_genai import GoogleGenerativeAIEmbeddings

_SA_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _load_sa_credentials():
    """Load Service Account credentials if credentials.json exists."""
    sa_file = Path("credentials.json")
    if sa_file.exists():
        return service_account.Credentials.from_service_account_file(
            str(sa_file), scopes=_SA_SCOPES
        )
    return None


def build_vertexai_embedding(config: dict):
    model_name = config.get("embedding_model", "text-embedding-004")

    project_env = config.get("embedding_project_id_env", "VERTEX_PROJECT_ID")
    location_env = config.get("embedding_location_env", "VERTEX_LOCATION")

    project_id = os.getenv(project_env)
    location = os.getenv(location_env)

    if not project_id:
        raise ValueError(f"缺少 GCP 專案 ID！請在 .env 檔案中設定 {project_env}")

    if not location:
        raise ValueError(f"缺少 GCP 區域！請在 .env 檔案中設定 {location_env}")

    dimensions = config.get("embedding_dimensions")

    print(f"[*] 初始化 Embedding: 載入 Vertex AI (模型: {model_name})")

    kwargs = dict(model=model_name, project=project_id, location=location, vertexai=True)
    if dimensions:
        kwargs["model_kwargs"] = {"output_dimensionality": int(dimensions)}

    creds = _load_sa_credentials()
    if creds:
        kwargs["credentials"] = creds

    return GoogleGenerativeAIEmbeddings(**kwargs)
