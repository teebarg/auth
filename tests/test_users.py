from fastapi.testclient import TestClient


class TestUser:
    def test_read_user_me(
        self, client: TestClient, normal_user_token_headers: dict[str, str]
    ):
        response = client.get("/api/users/me", headers=normal_user_token_headers)
        assert response.status_code == 200

    # def test_read_user_me_unauthenticated(self, unathenticated_client: TestClient):
    #     response = unathenticated_client.get("/api/users/me")
    #     # assert response.status_code == 401
