from worker.instagram import publish_reel_from_url


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if url.endswith("/ig-1/media"):
            return FakeResponse(200, {"id": "container-1"})
        if url.endswith("/ig-1/media_publish"):
            return FakeResponse(200, {"id": "media-1"})
        raise AssertionError(url)

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if url.endswith("/container-1"):
            return FakeResponse(200, {"status_code": "FINISHED"})
        if url.endswith("/media-1"):
            return FakeResponse(200, {"permalink": "https://www.instagram.com/reel/test/"})
        raise AssertionError(url)


def test_signed_storage_url_is_published_then_permalink_is_read():
    session = FakeSession()
    result = publish_reel_from_url(
        video_url="https://davyotbbhgnfxpgaglki.supabase.co/storage/v1/object/sign/pipeline-assets/final.mp4?token=signed",
        caption="실제 캡션",
        thumb_offset_ms=1234,
        ig_account_id="ig-1",
        access_token="secret-token",
        graph_version="v21.0",
        session=session,
        sleep=lambda _seconds: None,
    )

    assert result == {"media_id": "media-1", "permalink": "https://www.instagram.com/reel/test/"}
    create_params = session.posts[0][1]["data"]
    assert create_params["media_type"] == "REELS"
    assert create_params["thumb_offset"] == 1234
    assert create_params["video_url"].startswith("https://davyotbbhgnfxpgaglki.supabase.co/")
