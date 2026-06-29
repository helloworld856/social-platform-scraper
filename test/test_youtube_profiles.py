# -*- coding: utf-8 -*-
import threading
import pytest
from unittest.mock import MagicMock, patch
from googleapiclient.errors import HttpError
from src.platforms.youtube.profiles import (
    validate_and_normalize_youtube_url,
    classify_api_error,
    resolve_channel,
    run_channel_spider,
    RunStatus
)

def test_url_validation_success():
    # UC ID
    url, method, val = validate_and_normalize_youtube_url("youtube.com/channel/UC1234567890abcdef")
    assert url == "https://www.youtube.com/channel/UC1234567890abcdef"
    assert method == "channel_id"
    assert val == "UC1234567890abcdef"

    # Handle
    url, method, val = validate_and_normalize_youtube_url("https://www.youtube.com/@elonmusk")
    assert url == "https://www.youtube.com/channel/@elonmusk"
    assert method == "handle"
    assert val == "@elonmusk"

    # User
    url, method, val = validate_and_normalize_youtube_url("www.youtube.com/user/billgates")
    assert url == "https://www.youtube.com/user/billgates"
    assert method == "username"
    assert val == "billgates"

def test_url_validation_rejection():
    # Fake domain
    with pytest.raises(ValueError, match="不支持的域名"):
        validate_and_normalize_youtube_url("fake-youtube.com/channel/UC123")
        
    # Empty
    with pytest.raises(ValueError, match="URL为空"):
        validate_and_normalize_youtube_url("")

    # Video / Playlist / Shorts
    with pytest.raises(ValueError, match="不支持的资源链接类型"):
        validate_and_normalize_youtube_url("youtube.com/watch?v=123")
    with pytest.raises(ValueError, match="不支持的资源链接类型"):
        validate_and_normalize_youtube_url("youtube.com/playlist?list=123")
    with pytest.raises(ValueError, match="不支持的资源链接类型"):
        validate_and_normalize_youtube_url("youtube.com/shorts/123")

    # c or custom alias
    with pytest.raises(ValueError, match="不支持自定义别名"):
        validate_and_normalize_youtube_url("youtube.com/c/nvidia")

def test_api_error_classification():
    # Mock HttpError
    resp_quota = MagicMock(status=403)
    content_quota = b'{"error": {"message": "The request cannot be completed because you have exceeded your quota."}}'
    exc_quota = HttpError(resp_quota, content_quota)
    assert classify_api_error(exc_quota) == "quota_exhausted"

    resp_auth = MagicMock(status=401)
    exc_auth = HttpError(resp_auth, b"invalid key")
    assert classify_api_error(exc_auth) == "auth_invalid"

    resp_404 = MagicMock(status=404)
    exc_404 = HttpError(resp_404, b"not found")
    assert classify_api_error(exc_404) == "not_found"

    resp_503 = MagicMock(status=503)
    exc_503 = HttpError(resp_503, b"service unavailable")
    assert classify_api_error(exc_503) == "transient_network"

def test_key_rotation_restrict():
    client_pool = MagicMock()
    client_pool.next_client.return_value = True
    
    # 1. Quota error triggers rotation
    resp_quota = MagicMock(status=403)
    exc_quota = HttpError(resp_quota, b"quota exceeded")
    
    with patch('src.platforms.youtube.profiles.execute_with_retry') as mock_exec:
        call_count = 0
        def side_effect(req, cb):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise exc_quota
            return {"items": [{"id": "UC123", "snippet": {}, "statistics": {}}]}
        mock_exec.side_effect = side_effect
        
        resolve_channel(client_pool, "http://youtube.com/channel/UC123", "channel_id", "UC123")
        assert client_pool.next_client.call_count == 1

    # 2. Forbidden resource (other than quota) does NOT trigger rotation
    resp_forbidden = MagicMock(status=403)
    exc_forbidden = HttpError(resp_forbidden, b"access forbidden")
    client_pool.next_client.reset_mock()
    
    with patch('src.platforms.youtube.profiles.execute_with_retry') as mock_exec:
        def side_effect_forbidden(req, cb):
            raise exc_forbidden
        mock_exec.side_effect = side_effect_forbidden
        
        with pytest.raises(HttpError):
            resolve_channel(client_pool, "http://youtube.com/channel/UC123", "channel_id", "UC123")
        assert client_pool.next_client.call_count == 0

def test_run_channel_spider_cancellation(tmp_path):
    txt = tmp_path / "urls.txt"
    with open(txt, "w") as f:
        f.write("youtube.com/channel/UC1234567890abcdef\n")
        
    stop_event = threading.Event()
    stop_event.set()
    
    outcome = run_channel_spider(
        api_keys=["key"],
        txt_file_path=str(txt),
        log_callback=MagicMock(),
        finish_callback=MagicMock(),
        stop_event=stop_event,
        config={"max_parallel_tabs": 1}
    )
    
    assert outcome.status == RunStatus.CANCELLED
