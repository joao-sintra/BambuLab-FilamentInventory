from __future__ import annotations

import json
import requests

BASE_URL = "https://api.bambulab.com"


class AuthExpiredError(Exception):
    pass


class BambuClient:
    def __init__(self, email: str, password: str, token_path: str):
        self._email = email
        self._password = password
        self._token_path = token_path

    def login(self, verify_code_prompt) -> None:
        response = requests.post(
            f"{BASE_URL}/v1/user-service/user/login",
            json={"account": self._email, "password": self._password},
        )
        data = response.json()

        if response.status_code != 200 or data.get("loginType") == "verifyCode":
            code = verify_code_prompt()
            response = requests.post(
                f"{BASE_URL}/v1/user-service/user/login",
                json={"account": self._email, "code": code},
            )
            data = response.json()

        self._save_token(data["accessToken"], data["refreshToken"])

    def _save_token(self, token: str, refresh_token: str) -> None:
        with open(self._token_path, "w") as f:
            json.dump({"token": token, "refresh_token": refresh_token}, f)

    def _load_token(self) -> str:
        with open(self._token_path) as f:
            return json.load(f)["token"]

    def _load_refresh_token(self) -> str:
        with open(self._token_path) as f:
            return json.load(f)["refresh_token"]

    def refresh(self) -> bool:
        refresh_token = self._load_refresh_token()
        response = requests.post(
            f"{BASE_URL}/v1/user-service/user/login",
            json={"refreshToken": refresh_token},
        )
        if response.status_code != 200:
            return False
        data = response.json()
        self._save_token(data["accessToken"], data["refreshToken"])
        return True

    def get_tasks(self, limit: int = 20) -> list[dict]:
        token = self._load_token()
        response = requests.get(
            f"{BASE_URL}/v1/user-service/my/tasks",
            params={"limit": limit},
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            raise AuthExpiredError("Bambu token expired or invalid")
        return response.json()["hits"]
