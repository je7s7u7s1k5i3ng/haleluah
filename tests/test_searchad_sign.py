import base64
import hashlib
import hmac

from item_scout.clients.searchad import RelatedKeyword, sign


def test_sign_matches_hmac_sha256_base64():
    ts, method, uri, secret = "1700000000000", "GET", "/keywordstool", "s3cr3t"
    expected = base64.b64encode(
        hmac.new(
            secret.encode(),
            f"{ts}.{method}.{uri}".encode(),
            hashlib.sha256,
        ).digest()
    ).decode()
    assert sign(ts, method, uri, secret) == expected


def test_sign_is_case_insensitive_on_method():
    ts, uri, secret = "1700000000000", "/keywordstool", "s3cr3t"
    assert sign(ts, "get", uri, secret) == sign(ts, "GET", uri, secret)


def test_related_keyword_handles_low_volume_marker():
    rk = RelatedKeyword.from_api(
        {
            "relKeyword": "무선이어폰",
            "monthlyPcQcCnt": "< 10",
            "monthlyMobileQcCnt": 12300,
            "monthlyAvePcClkCnt": 3.5,
            "monthlyAveMobileClkCnt": 50.0,
            "monthlyAvePcCtr": 0.5,
            "monthlyAveMobileCtr": 1.2,
            "plAvgDepth": 15,
            "compIdx": "높음",
        }
    )
    assert rk.keyword == "무선이어폰"
    assert rk.monthly_pc_qc == 5
    assert rk.monthly_mobile_qc == 12300
    assert rk.total_qc == 12305
    assert rk.comp_idx == "높음"
