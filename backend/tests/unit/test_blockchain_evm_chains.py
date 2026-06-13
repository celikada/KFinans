"""EVM zincir servisleri birim testleri: Ethereum + Avalanche C-Chain + Sonic.

web3.py 7.x AsyncHTTPProvider aiohttp kullanir (httpx degil) — respx
intercept etmez. Bu yuzden `AsyncWeb3` sinifi her servis modulunde
fake bir sinifla patch'lenir; native get_balance + ERC-20 contract
balanceOf + Sonic SFC validator stake/rewards cagrilari taklit edilir.

Ethplorer (Ethereum ERC-20) ve Glacier (Avalanche P-Chain) HTTP cagrilari
respx ile mock'lanir (httpx tabanli).
"""

from decimal import Decimal

import pytest

import app.services.blockchain.avalanche as avalanche_mod
import app.services.blockchain.ethereum as eth_mod
import app.services.blockchain.sonic as sonic_mod
from app.services.blockchain.avalanche import AvalancheCChainService
from app.services.blockchain.ethereum import EthereumService
from app.services.blockchain.evm_tokens import TokenDef
from app.services.blockchain.sonic import SonicService

# Gercek checksum'lanabilir EVM adresi (web3 to_checksum_address gercek calisir)
EVM_ADDR = "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be"


# ─── Fake AsyncWeb3 altyapisi ──────────────────────────────────────────


class _FakeFn:
    """contract.functions.<name>(*args) cagrisini taklit eder; .call() coroutine."""

    def __init__(self, name, resolver):
        self._name = name
        self._resolver = resolver
        self._args = ()

    def __call__(self, *args):
        self._args = args
        return self

    async def call(self):
        return self._resolver(self._name, self._args)


class _FakeFunctions:
    def __init__(self, resolver):
        self._resolver = resolver

    def __getattr__(self, name):
        return _FakeFn(name, self._resolver)


class _FakeContract:
    def __init__(self, resolver):
        self.functions = _FakeFunctions(resolver)


class _FakeEth:
    def __init__(self, balance_wei, balance_exc, contract_resolver):
        self._balance_wei = balance_wei
        self._balance_exc = balance_exc
        self._contract_resolver = contract_resolver

    async def get_balance(self, checksum):
        if self._balance_exc is not None:
            raise self._balance_exc
        return self._balance_wei

    def contract(self, address=None, abi=None):
        return _FakeContract(self._contract_resolver)


def make_fake_web3_class(balance_wei=0, balance_exc=None, contract_resolver=None):
    """Modul seviyesindeki AsyncWeb3 yerine gecirilecek fake sinif uretir.

    - balance_wei: eth.get_balance donus degeri (wei)
    - balance_exc: verilirse get_balance bu exception'i firlatir (RPC fail)
    - contract_resolver: (fn_name, args) -> int (SFC / ERC-20 cagrilari)
    """
    if contract_resolver is None:

        def contract_resolver(name, args):  # noqa: ANN001
            return 0

    real_checksum = eth_mod.AsyncWeb3.to_checksum_address

    class _FakeAsyncWeb3:
        def __init__(self, provider):
            self.provider = provider
            self.eth = _FakeEth(balance_wei, balance_exc, contract_resolver)

        # web3 servisleri AsyncWeb3.AsyncHTTPProvider(...) cagirir
        @staticmethod
        def AsyncHTTPProvider(url, request_kwargs=None):  # noqa: N802
            return ("provider", url)

        # to_checksum_address bir staticmethod; gercek implementasyonu kullan
        to_checksum_address = staticmethod(real_checksum)

    return _FakeAsyncWeb3


# ─── Ethereum ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ethereum_fetch_native_only(monkeypatch):
    """ETH bakiyesi > 0; ERC-20 yok -> tek AssetData (ETH)."""
    fake = make_fake_web3_class(balance_wei=2 * 10**18)
    monkeypatch.setattr(eth_mod, "AsyncWeb3", fake)

    async def _no_tokens(addr):
        return []

    monkeypatch.setattr(eth_mod, "fetch_ethereum_tokens_via_ethplorer", _no_tokens)

    svc = EthereumService(EVM_ADDR, wallet_address_id="w1")
    assets = await svc.fetch()
    assert len(assets) == 1
    a = assets[0]
    assert a.symbol == "ETH"
    assert a.name == "Ethereum"
    assert a.provider == "ethereum"
    assert a.asset_type == "crypto"
    assert a.liquid_quantity == Decimal("2")
    assert a.wallet_address_id == "w1"


@pytest.mark.asyncio
async def test_ethereum_fetch_with_erc20_tokens(monkeypatch):
    """Native ETH + 2 ERC-20 token -> 3 AssetData."""
    fake = make_fake_web3_class(balance_wei=10**18)
    monkeypatch.setattr(eth_mod, "AsyncWeb3", fake)

    async def _tokens(addr):
        return [
            (TokenDef("USDC", "USD Coin", "0xa0b8", 6), Decimal("100")),
            (TokenDef("DAI", "Dai", "0x6b17", 18), Decimal("50")),
        ]

    monkeypatch.setattr(eth_mod, "fetch_ethereum_tokens_via_ethplorer", _tokens)

    svc = EthereumService(EVM_ADDR)
    assets = await svc.fetch()
    symbols = [a.symbol for a in assets]
    assert symbols == ["ETH", "USDC", "DAI"]
    assert all(a.provider == "ethereum" for a in assets)


@pytest.mark.asyncio
async def test_ethereum_zero_balance_no_native_asset(monkeypatch):
    """ETH bakiyesi 0 ise ETH AssetData uretilmez; sadece token'lar."""
    fake = make_fake_web3_class(balance_wei=0)
    monkeypatch.setattr(eth_mod, "AsyncWeb3", fake)

    async def _tokens(addr):
        return [(TokenDef("USDC", "USD Coin", "0xa0b8", 6), Decimal("5"))]

    monkeypatch.setattr(eth_mod, "fetch_ethereum_tokens_via_ethplorer", _tokens)

    svc = EthereumService(EVM_ADDR)
    assets = await svc.fetch()
    assert [a.symbol for a in assets] == ["USDC"]


@pytest.mark.asyncio
async def test_ethereum_all_rpcs_fail_returns_empty(monkeypatch):
    """Tum RPC'ler get_balance'da patlar -> bos liste (balance_wei None)."""
    fake = make_fake_web3_class(balance_exc=RuntimeError("rpc down"))
    monkeypatch.setattr(eth_mod, "AsyncWeb3", fake)

    svc = EthereumService(EVM_ADDR)
    assets = await svc.fetch()
    assert assets == []


@pytest.mark.asyncio
async def test_ethereum_first_rpc_fails_fallback_succeeds(monkeypatch):
    """Ilk RPC get_balance'da patlar, ikincisi basarili olur (fallback)."""
    call_state = {"n": 0}
    real_checksum = eth_mod.AsyncWeb3.to_checksum_address

    class _FlakyWeb3:
        def __init__(self, provider):
            self.eth = self._Eth()

        class _Eth:
            async def get_balance(self, checksum):
                call_state["n"] += 1
                if call_state["n"] == 1:
                    raise RuntimeError("first rpc down")
                return 3 * 10**18

            def contract(self, address=None, abi=None):
                return _FakeContract(lambda n, a: 0)

        @staticmethod
        def AsyncHTTPProvider(url, request_kwargs=None):  # noqa: N802
            return url

        to_checksum_address = staticmethod(real_checksum)

    monkeypatch.setattr(eth_mod, "AsyncWeb3", _FlakyWeb3)

    async def _no_tokens(addr):
        return []

    monkeypatch.setattr(eth_mod, "fetch_ethereum_tokens_via_ethplorer", _no_tokens)

    svc = EthereumService(EVM_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].liquid_quantity == Decimal("3")
    assert call_state["n"] == 2  # ilk fail, ikinci basarili


@pytest.mark.asyncio
async def test_ethereum_token_scan_exception_swallowed(monkeypatch):
    """ERC-20 tarama exception firlatirsa fetch yine ETH'i doner (best-effort)."""
    fake = make_fake_web3_class(balance_wei=10**18)
    monkeypatch.setattr(eth_mod, "AsyncWeb3", fake)

    async def _boom(addr):
        raise RuntimeError("ethplorer down")

    monkeypatch.setattr(eth_mod, "fetch_ethereum_tokens_via_ethplorer", _boom)

    svc = EthereumService(EVM_ADDR)
    assets = await svc.fetch()
    assert [a.symbol for a in assets] == ["ETH"]


@pytest.mark.asyncio
async def test_ethereum_health_check_true(monkeypatch):
    fake = make_fake_web3_class(balance_wei=10**18)
    monkeypatch.setattr(eth_mod, "AsyncWeb3", fake)

    async def _no_tokens(addr):
        return []

    monkeypatch.setattr(eth_mod, "fetch_ethereum_tokens_via_ethplorer", _no_tokens)
    svc = EthereumService(EVM_ADDR)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_ethereum_health_check_false_on_fetch_exception(monkeypatch):
    """fetch() icinde beklenmedik exception -> health_check False."""
    svc = EthereumService(EVM_ADDR)

    async def _boom():
        raise RuntimeError("unexpected")

    monkeypatch.setattr(svc, "fetch", _boom)
    assert await svc.health_check() is False


# ─── Avalanche C-Chain ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_avalanche_c_fetch_native_only(monkeypatch):
    """Liquid AVAX > 0, token yok -> tek AVAX AssetData."""
    fake = make_fake_web3_class(balance_wei=5 * 10**18)
    monkeypatch.setattr(avalanche_mod, "AsyncWeb3", fake)

    async def _no_tokens(w3, address, tokens):
        return []

    monkeypatch.setattr(avalanche_mod, "fetch_token_balances", _no_tokens)

    svc = AvalancheCChainService(EVM_ADDR, wallet_address_id="wc")
    assets = await svc.fetch()
    assert len(assets) == 1
    a = assets[0]
    assert a.symbol == "AVAX"
    assert a.provider == "avalanche_c"
    assert a.liquid_quantity == Decimal("5")
    assert a.wallet_address_id == "wc"


@pytest.mark.asyncio
async def test_avalanche_c_fetch_with_tokens(monkeypatch):
    """Native + sAVAX token -> 2 AssetData."""
    fake = make_fake_web3_class(balance_wei=10**18)
    monkeypatch.setattr(avalanche_mod, "AsyncWeb3", fake)

    async def _tokens(w3, address, tokens):
        return [(TokenDef("sAVAX", "Staked AVAX", "0x2b2c", 18), Decimal("2.5"))]

    monkeypatch.setattr(avalanche_mod, "fetch_token_balances", _tokens)

    svc = AvalancheCChainService(EVM_ADDR)
    assets = await svc.fetch()
    assert [a.symbol for a in assets] == ["AVAX", "sAVAX"]


@pytest.mark.asyncio
async def test_avalanche_c_zero_balance_only_tokens(monkeypatch):
    """Liquid 0 -> AVAX uretilmez, token devam."""
    fake = make_fake_web3_class(balance_wei=0)
    monkeypatch.setattr(avalanche_mod, "AsyncWeb3", fake)

    async def _tokens(w3, address, tokens):
        return [(TokenDef("USDC", "USD Coin", "0xb97e", 6), Decimal("9"))]

    monkeypatch.setattr(avalanche_mod, "fetch_token_balances", _tokens)

    svc = AvalancheCChainService(EVM_ADDR)
    assets = await svc.fetch()
    assert [a.symbol for a in assets] == ["USDC"]


@pytest.mark.asyncio
async def test_avalanche_c_all_rpcs_fail_returns_empty(monkeypatch):
    fake = make_fake_web3_class(balance_exc=RuntimeError("avax rpc down"))
    monkeypatch.setattr(avalanche_mod, "AsyncWeb3", fake)

    svc = AvalancheCChainService(EVM_ADDR)
    assets = await svc.fetch()
    assert assets == []


@pytest.mark.asyncio
async def test_avalanche_c_token_scan_exception_swallowed(monkeypatch):
    fake = make_fake_web3_class(balance_wei=10**18)
    monkeypatch.setattr(avalanche_mod, "AsyncWeb3", fake)

    async def _boom(w3, address, tokens):
        raise RuntimeError("token scan down")

    monkeypatch.setattr(avalanche_mod, "fetch_token_balances", _boom)

    svc = AvalancheCChainService(EVM_ADDR)
    assets = await svc.fetch()
    assert [a.symbol for a in assets] == ["AVAX"]


@pytest.mark.asyncio
async def test_avalanche_c_health_check_true(monkeypatch):
    fake = make_fake_web3_class(balance_wei=10**18)
    # health_check self._w3'u kullanir; once fetch ile set edilmeli
    monkeypatch.setattr(avalanche_mod, "AsyncWeb3", fake)

    async def _no_tokens(w3, address, tokens):
        return []

    monkeypatch.setattr(avalanche_mod, "fetch_token_balances", _no_tokens)
    svc = AvalancheCChainService(EVM_ADDR)
    await svc.fetch()  # _w3 set edilir
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_avalanche_c_health_check_false_no_w3(monkeypatch):
    """fetch hic cagrilmamis -> self._w3 yok -> health_check False."""
    svc = AvalancheCChainService(EVM_ADDR)
    assert await svc.health_check() is False


# ─── Sonic ─────────────────────────────────────────────────────────────


def _sonic_resolver(stake_map, rewards_map, last_validator_id):
    """SFC contract fonksiyon cevaplari (wei).

    stake_map / rewards_map: {validator_id: wei}
    """

    def resolver(name, args):
        if name == "lastValidatorID":
            return last_validator_id
        if name == "getStake":
            vid = args[1]
            return stake_map.get(vid, 0)
        if name == "pendingRewards":
            vid = args[1]
            return rewards_map.get(vid, 0)
        return 0

    return resolver


@pytest.mark.asyncio
async def test_sonic_fetch_liquid_and_stake(monkeypatch):
    """Liquid S + 2 validator stake + rewards -> staked_crypto AssetData."""
    resolver = _sonic_resolver(
        stake_map={1: 10 * 10**18, 2: 5 * 10**18},
        rewards_map={1: 10**18, 2: 0},
        last_validator_id=2,
    )
    fake = make_fake_web3_class(balance_wei=3 * 10**18, contract_resolver=resolver)
    monkeypatch.setattr(sonic_mod, "AsyncWeb3", fake)

    svc = SonicService(EVM_ADDR, wallet_address_id="ws")
    assets = await svc.fetch()
    assert len(assets) == 1
    a = assets[0]
    assert a.symbol == "S"
    assert a.name == "Sonic"
    assert a.provider == "sonic"
    assert a.asset_type == "staked_crypto"
    assert a.liquid_quantity == Decimal("3")
    assert a.staked_quantity == Decimal("15")  # 10 + 5
    assert a.pending_rewards == Decimal("1")
    assert a.wallet_address_id == "ws"


@pytest.mark.asyncio
async def test_sonic_fetch_liquid_only_no_stake(monkeypatch):
    """Stake yok -> asset_type=crypto."""
    resolver = _sonic_resolver(stake_map={}, rewards_map={}, last_validator_id=3)
    fake = make_fake_web3_class(balance_wei=2 * 10**18, contract_resolver=resolver)
    monkeypatch.setattr(sonic_mod, "AsyncWeb3", fake)

    svc = SonicService(EVM_ADDR)
    assets = await svc.fetch()
    assert len(assets) == 1
    assert assets[0].asset_type == "crypto"
    assert assets[0].staked_quantity == Decimal("0")


@pytest.mark.asyncio
async def test_sonic_fetch_zero_everything_returns_empty(monkeypatch):
    """Liquid 0 + stake 0 -> bos liste."""
    resolver = _sonic_resolver(stake_map={}, rewards_map={}, last_validator_id=1)
    fake = make_fake_web3_class(balance_wei=0, contract_resolver=resolver)
    monkeypatch.setattr(sonic_mod, "AsyncWeb3", fake)

    svc = SonicService(EVM_ADDR)
    assets = await svc.fetch()
    assert assets == []


@pytest.mark.asyncio
async def test_sonic_validator_query_exception_returns_zero(monkeypatch):
    """getStake bir validator'da patlar -> o validator 0,0 sayilir (try/except)."""

    def resolver(name, args):
        if name == "lastValidatorID":
            return 2
        if name == "getStake":
            if args[1] == 1:
                raise RuntimeError("validator query fail")
            return 4 * 10**18
        if name == "pendingRewards":
            return 0
        return 0

    fake = make_fake_web3_class(balance_wei=10**18, contract_resolver=resolver)
    monkeypatch.setattr(sonic_mod, "AsyncWeb3", fake)

    svc = SonicService(EVM_ADDR)
    assets = await svc.fetch()
    # vid=1 exception -> 0; vid=2 -> 4 S
    assert assets[0].staked_quantity == Decimal("4")


@pytest.mark.asyncio
async def test_sonic_health_check_true(monkeypatch):
    fake = make_fake_web3_class(balance_wei=10**18)
    monkeypatch.setattr(sonic_mod, "AsyncWeb3", fake)
    svc = SonicService(EVM_ADDR)
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_sonic_health_check_false_on_rpc_error(monkeypatch):
    fake = make_fake_web3_class(balance_exc=RuntimeError("sonic rpc down"))
    monkeypatch.setattr(sonic_mod, "AsyncWeb3", fake)
    svc = SonicService(EVM_ADDR)
    assert await svc.health_check() is False
