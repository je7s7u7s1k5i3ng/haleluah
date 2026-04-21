import httpx
import pytest
import respx

from item_scout.clients.shopping import BASE_URL, ShoppingClient


@pytest.mark.asyncio
@respx.mock
async def test_search_parses_total_and_items():
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 12345,
                "start": 1,
                "display": 1,
                "items": [
                    {
                        "title": "<b>무선</b>이어폰",
                        "link": "https://example.com/p/1",
                        "lprice": "15900",
                        "mallName": "샵",
                        "productId": "P1",
                        "productType": "1",
                        "brand": "B",
                        "maker": "M",
                        "category1": "디지털",
                        "category2": "",
                        "category3": "",
                        "category4": "",
                    }
                ],
            },
        )
    )
    async with ShoppingClient("id", "secret") as c:
        res = await c.search("무선이어폰", display=1)
    assert res.total == 12345
    assert res.items[0].title == "무선이어폰"
    assert res.items[0].lprice == 15900


@pytest.mark.asyncio
@respx.mock
async def test_total_only_uses_display_1():
    route = respx.get(BASE_URL).mock(
        return_value=httpx.Response(200, json={"total": 7, "items": []})
    )
    async with ShoppingClient("id", "secret") as c:
        total = await c.total_only("가방")
    assert total == 7
    assert route.calls.last.request.url.params["display"] == "1"
