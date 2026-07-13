import pytest

from worker.llm import (
    AFFILIATE_DISCLOSURE,
    LlmError,
    parse_json_content,
    validate_content_package,
)


def test_json_parser_accepts_a_single_markdown_fence():
    assert parse_json_content('```json\n{"hook":"이게 뭐지?"}\n```') == {"hook": "이게 뭐지?"}


def test_content_package_validates_script_cover_and_appends_disclosure():
    package = validate_content_package({
        "hook": "장난감처럼 보이죠?",
        "narration": "그런데 손에 쥐고 돌리면 좁은 틈까지 한 번에 정리되는 회전 선반입니다.",
        "caption": "좁은 책상에 자꾸 물건이 쌓인다면 확인해 보세요.",
        "cover_lines": ["장난감인 줄 알았죠?", "책상 정리템입니다"],
        "hashtags": ["신기템", "생활용품"],
    })

    assert package["caption"].endswith(AFFILIATE_DISCLOSURE)
    assert package["cover_lines"] == ["장난감인 줄 알았죠?", "책상 정리템입니다"]


@pytest.mark.parametrize("payload", [
    {"hook": "훅", "narration": "숫자 1번이 들어갑니다.", "caption": "캡션", "cover_lines": ["한 줄", "두 줄"]},
    {"hook": "훅", "narration": "충분히 재미있는 설명 문장입니다.", "caption": "캡션", "cover_lines": ["한 줄"]},
    {"hook": "", "narration": "충분히 재미있는 설명 문장입니다.", "caption": "캡션", "cover_lines": ["한 줄", "두 줄"]},
])
def test_content_package_rejects_invalid_or_digit_narration(payload):
    with pytest.raises(LlmError):
        validate_content_package(payload)


def test_json_parser_rejects_trailing_non_json_content():
    with pytest.raises(LlmError):
        parse_json_content('{"hook":"정상"}\n추가 설명')
