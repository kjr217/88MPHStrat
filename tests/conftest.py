import pytest
from brownie import config
from brownie import Contract


@pytest.fixture
def gov(accounts):
    yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)


@pytest.fixture
def user(accounts):
    yield accounts[0]

@pytest.fixture
def user217(accounts):
    yield accounts[9]

@pytest.fixture
def user8(accounts):
    yield accounts[8]

@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[2]


@pytest.fixture
def management(accounts):
    yield accounts[3]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[5]


@pytest.fixture
def token():
    token_address = "0x8888801af4d980682e47f1a9036e589479e835c5"  # this should be the address of the ERC-20 used by the strategy/vault (DAI)
    yield Contract(token_address)

@pytest.fixture
def dai():
    token_address = "0x6B175474E89094C44Da98b954EedeAC495271d0F"  # this should be the address of the ERC-20 used by the strategy/vault (DAI)
    yield Contract(token_address)

@pytest.fixture
def amount(accounts, token, user):
    amount = 1_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x98df8d9e56b51e4ea8aa9b57f8a5df7a044234e1", force=True)
    token.transfer(user, amount, {"from": reserve})
    yield amount

@pytest.fixture
def amount217(accounts, token, user217):
    amount = 2_170 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x98df8d9e56b51e4ea8aa9b57f8a5df7a044234e1", force=True)
    token.transfer(user217, amount, {"from": reserve})
    yield amount

@pytest.fixture
def amount8(accounts, token, user8):
    amount = 2_170 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x98df8d9e56b51e4ea8aa9b57f8a5df7a044234e1", force=True)
    token.transfer(user8, amount, {"from": reserve})
    yield amount

@pytest.fixture
def weth():
    token_address = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    yield Contract(token_address)


@pytest.fixture
def weth_amout(user, weth):
    weth_amout = 10 ** weth.decimals()
    user.transfer(weth, weth_amout)
    yield weth_amout


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture
def strategy(strategist, keeper, vault, Strategy, gov):
    strategy = strategist.deploy(Strategy, vault)
    strategy.setKeeper(keeper)
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    yield strategy


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 1e-5
