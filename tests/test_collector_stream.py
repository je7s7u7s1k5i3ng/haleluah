import pytest

from item_scout.clients.searchad import RelatedKeyword
from item_scout.scout.checkpoint import Checkpoint
from item_scout.scout.collector import attach_product_counts


class FakeShop:
    def __init__(self, totals):
        self._totals = totals
        self.calls = 0

    async def total_only(self, kw):
        self.calls += 1
        return self._totals.get(kw, 0)


def _rel(k, pc=100, mo=200):
    return RelatedKeyword(
        keyword=k,
        monthly_pc_qc=pc,
        monthly_mobile_qc=mo,
        monthly_ave_pc_clk=0,
        monthly_ave_mobile_clk=0,
        monthly_ave_pc_ctr=0,
        monthly_ave_mobile_ctr=0,
        pl_avg_depth=10,
        comp_idx="중간",
    )


@pytest.mark.asyncio
async def test_attach_product_counts_streams_results(tmp_path):
    related = {f"kw{i}": _rel(f"kw{i}") for i in range(5)}
    totals = {f"kw{i}": (i + 1) * 100 for i in range(5)}
    shop = FakeShop(totals)

    got = []
    async for m in attach_product_counts(shop, related, concurrency=3):
        got.append(m)

    assert len(got) == 5
    kws = {m.keyword for m in got}
    assert kws == {"kw0", "kw1", "kw2", "kw3", "kw4"}
    for m in got:
        assert m.total_products == totals[m.keyword]


@pytest.mark.asyncio
async def test_checkpoint_skips_already_done(tmp_path):
    related = {f"k{i}": _rel(f"k{i}") for i in range(4)}
    shop = FakeShop({f"k{i}": 10 for i in range(4)})

    ckpt_path = tmp_path / "c.jsonl"
    with Checkpoint(ckpt_path) as ckpt:
        ckpt.mark("k0")
        ckpt.mark("k1")

    with Checkpoint(ckpt_path) as ckpt:
        assert ckpt.done("k0")
        assert not ckpt.done("k2")
        got = []
        async for m in attach_product_counts(shop, related, concurrency=2, checkpoint=ckpt):
            got.append(m)

    # 2개만 새로 수집
    assert len(got) == 2
    assert {m.keyword for m in got} == {"k2", "k3"}
    assert shop.calls == 2
