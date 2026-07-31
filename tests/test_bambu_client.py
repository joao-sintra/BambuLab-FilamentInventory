import json
from unittest.mock import patch, MagicMock
from bambu_inventory.bambu_client import BambuClient, AuthExpiredError


def test_login_without_verification_saves_token(tmp_path):
    token_path = str(tmp_path / "token.json")
    client = BambuClient("a@b.com", "pw", token_path)

    login_response = MagicMock(status_code=200)
    login_response.json.return_value = {"accessToken": "tok123", "refreshToken": "ref123"}

    with patch("bambu_inventory.bambu_client.requests.post", return_value=login_response) as mock_post:
        client.login(verify_code_prompt=lambda: (_ for _ in ()).throw(AssertionError("should not be called")))

    assert mock_post.call_count == 1
    with open(token_path) as f:
        saved = json.load(f)
    assert saved == {"token": "tok123", "refresh_token": "ref123"}


def test_login_with_verification_code_calls_second_endpoint(tmp_path):
    token_path = str(tmp_path / "token.json")
    client = BambuClient("a@b.com", "pw", token_path)

    needs_code_response = MagicMock(status_code=400)
    needs_code_response.json.return_value = {"loginType": "verifyCode"}

    verified_response = MagicMock(status_code=200)
    verified_response.json.return_value = {"accessToken": "tok456", "refreshToken": "ref456"}

    with patch("bambu_inventory.bambu_client.requests.post", side_effect=[needs_code_response, verified_response]) as mock_post:
        client.login(verify_code_prompt=lambda: "654321")

    assert mock_post.call_count == 2
    with open(token_path) as f:
        saved = json.load(f)
    assert saved == {"token": "tok456", "refresh_token": "ref456"}


def test_get_tasks_returns_hits_list(tmp_path):
    token_path = str(tmp_path / "token.json")
    with open(token_path, "w") as f:
        json.dump({"token": "tok123", "refresh_token": "ref123"}, f)
    client = BambuClient("a@b.com", "pw", token_path)

    tasks_response = MagicMock(status_code=200)
    tasks_response.json.return_value = {"hits": [{"id": "1"}, {"id": "2"}]}

    with patch("bambu_inventory.bambu_client.requests.get", return_value=tasks_response) as mock_get:
        result = client.get_tasks(limit=20)

    assert result == [{"id": "1"}, {"id": "2"}]
    called_headers = mock_get.call_args.kwargs["headers"]
    assert called_headers["Authorization"] == "Bearer tok123"


def test_get_tasks_raises_auth_expired_on_401(tmp_path):
    token_path = str(tmp_path / "token.json")
    with open(token_path, "w") as f:
        json.dump({"token": "expired", "refresh_token": "ref123"}, f)
    client = BambuClient("a@b.com", "pw", token_path)

    unauthorized_response = MagicMock(status_code=401)

    with patch("bambu_inventory.bambu_client.requests.get", return_value=unauthorized_response):
        try:
            client.get_tasks()
            assert False, "expected AuthExpiredError"
        except AuthExpiredError:
            pass
