import pytest

from worker.pipeline_handlers import (
    CLOUD_PIPELINE_TYPES,
    CloudPipelineHandlers,
    PipelineHandlerError,
    PipelineInputRequired,
)


class FakeClient:
    def __init__(self, product=None):
        self.product = product or {
            "id": 4,
            "title": "수집 대기",
            "coupang_url": "https://link.coupang.com/a/test",
            "ali_url": None,
        }
        self.product_updates = []

    def get_product(self, product_id):
        return self.product if product_id == self.product["id"] else None

    def update_product(self, product_id, **fields):
        self.product_updates.append((product_id, fields))


def test_cloud_pipeline_declares_every_remote_content_stage():
    assert CLOUD_PIPELINE_TYPES == {
        "source_product", "source_video", "analyze_video", "generate_script",
        "generate_voice", "compose_video", "generate_cover", "generate_caption",
        "publish_reel", "export_products",
    }


def test_source_product_updates_only_parsed_public_metadata():
    client = FakeClient()
    handlers = CloudPipelineHandlers(
        client,
        product_fetcher=lambda url: {
            "title": "회전 책상 정리 선반",
            "image_url": "https://image.coupangcdn.com/item.jpg",
            "description": "회전해서 쓰는 선반",
            "price": 28500,
        },
    )

    result = handlers.handle({
        "id": "job-product", "product_id": 4, "type": "source_product",
        "payload": {"coupang_url": "https://link.coupang.com/a/test"},
    })

    assert result["title"] == "회전 책상 정리 선반"
    assert client.product_updates == [(4, {
        "title": "회전 책상 정리 선반",
        "image_url": "https://image.coupangcdn.com/item.jpg",
        "price": 28500,
        "local_snapshot": {"cloud": {"description": "회전해서 쓰는 선반"}},
    })]


def test_source_product_can_resume_with_admin_supplied_metadata_without_fetching_coupang():
    client = FakeClient()

    def forbidden_fetch(_url):
        raise AssertionError("manual metadata must skip Coupang fetch")

    handlers = CloudPipelineHandlers(client, product_fetcher=forbidden_fetch)
    result = handlers.handle({
        "id": "job-product", "product_id": 4, "type": "source_product",
        "payload": {
            "product_title": "회전 정리 선반",
            "product_description": "책상 위를 깔끔하게 정리합니다.",
            "product_price": 19900,
            "product_image_url": "https://example.com/product.jpg",
        },
    })

    assert result == {
        "title": "회전 정리 선반",
        "price": 19900,
        "image_url": "https://example.com/product.jpg",
    }
    assert client.product_updates == [(4, {
        "title": "회전 정리 선반",
        "image_url": "https://example.com/product.jpg",
        "price": 19900,
        "local_snapshot": {"cloud": {"description": "책상 위를 깔끔하게 정리합니다."}},
    })]


def test_video_source_without_ali_url_or_uploaded_asset_waits_for_admin():
    handlers = CloudPipelineHandlers(FakeClient())

    with pytest.raises(PipelineInputRequired) as caught:
        handlers.handle({
            "id": "job-video", "product_id": 4, "type": "source_video", "payload": {},
        })

    assert caught.value.input_kind == "ali_url_or_video"


def test_unknown_cloud_handler_is_rejected():
    with pytest.raises(PipelineHandlerError):
        CloudPipelineHandlers(FakeClient()).handle({
            "id": "job", "product_id": 4, "type": "delete_everything", "payload": {},
        })
