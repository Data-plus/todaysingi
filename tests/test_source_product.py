import pytest

from worker.source_product import SourceInputRequired, parse_coupang_product, validate_coupang_url


def test_coupang_open_graph_and_json_ld_are_parsed():
    html = """
    <html><head>
      <meta property="og:title" content="360도 회전 책상 정리 선반" />
      <meta property="og:image" content="https://image.coupangcdn.com/test.jpg" />
      <meta property="og:description" content="좁은 책상을 정리하는 회전 선반" />
      <script type="application/ld+json">{"@type":"Product","offers":{"price":"28500"}}</script>
    </head></html>
    """

    assert parse_coupang_product(html) == {
        "title": "360도 회전 책상 정리 선반",
        "image_url": "https://image.coupangcdn.com/test.jpg",
        "description": "좁은 책상을 정리하는 회전 선반",
        "price": 28500,
    }


@pytest.mark.parametrize("url", [
    "http://www.coupang.com/vp/products/1",
    "https://evil.example/coupang",
    "file:///etc/passwd",
])
def test_only_https_coupang_hosts_are_allowed(url):
    with pytest.raises(ValueError):
        validate_coupang_url(url)


def test_bot_block_page_becomes_a_manual_input_boundary():
    with pytest.raises(SourceInputRequired, match="차단"):
        parse_coupang_product("<html><title>Access Denied</title><body>captcha</body></html>")
