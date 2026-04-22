import logging
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path("config/token.json")
CLIENT_SECRET_PATH = Path("config/client_secret.json")


class YouTubeUploader:
    def __init__(self, config: dict):
        self.config = config["youtube"]
        self._service = None

    def _authenticate(self):
        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CLIENT_SECRET_PATH.exists():
                    raise FileNotFoundError(
                        f"YouTube API 인증 파일이 없습니다: {CLIENT_SECRET_PATH}\n"
                        "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 다운로드하세요."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CLIENT_SECRET_PATH), SCOPES
                )
                creds = flow.run_local_server(port=0)

            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_PATH.write_text(creds.to_json())

        self._service = build("youtube", "v3", credentials=creds)

    @property
    def service(self):
        if self._service is None:
            self._authenticate()
        return self._service

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
    ) -> str:
        all_tags = list(set(tags + self.config.get("default_tags", [])))

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": all_tags,
                "categoryId": self.config.get("category_id", "22"),
            },
            "status": {
                "privacyStatus": self.config.get("privacy_status", "public"),
                "selfDeclaredMadeForKids": self.config.get("made_for_kids", False),
                "shorts": {"shortsEligibility": "eligible"},
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=256 * 1024,
        )

        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        retry = 0
        while response is None:
            try:
                _, response = request.next_chunk()
            except Exception as e:
                retry += 1
                if retry > 3:
                    raise
                logger.warning("Upload retry %d: %s", retry, e)
                time.sleep(2 ** retry)

        video_id = response["id"]
        logger.info("Uploaded: https://youtube.com/shorts/%s", video_id)
        return video_id

    def upload_batch(
        self, videos: list[dict], delay_between: float = 2.0
    ) -> list[str]:
        video_ids = []
        for v in videos:
            try:
                vid = self.upload(
                    video_path=Path(v["path"]),
                    title=v["title"],
                    description=v["description"],
                    tags=v.get("tags", []),
                )
                video_ids.append(vid)
                time.sleep(delay_between)
            except Exception as e:
                logger.error("Upload failed for %s: %s", v["path"], e)
        return video_ids
