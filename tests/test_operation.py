import brownie
from brownie import Contract, chain
import pytest

def test_profitable_harvest(
    accounts, dai, gov, token, vault, strategy, user, user217, user8, strategist, amount, amount217, amount8, RELATIVE_APPROX, chain
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    token.approve(vault.address, amount217, {"from": user217})
    vault.deposit(amount, {"from": user})
    vault.deposit(amount217, {"from": user217})
    assert token.balanceOf(vault.address) == amount + amount217

    # Harvest 1: Send funds through the strategy
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount + amount217
    before_pps = vault.pricePerShare()
    # TODO: Add some code before harvest #2 to simulate earning yield
    sleepAndHarvest(10, strategy, gov, vault, dai)
    # Harvest 2: Realize profit
    strategy.harvest()
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault
    assert vault.pricePerShare() >= before_pps
    # Withdraws should not fail
    vault.withdraw(amount, {"from": user})
    vault.withdraw(amount217, {"from": user217})

    # Depositors after withdraw should have a profit or gotten the original amount
    assert token.balanceOf(user) >= amount
    assert token.balanceOf(user217) >= amount217

    # Make sure it isnt less than 1 after depositors withdrew
    assert vault.pricePerShare() / 1e18 >= 1


def test_operation(
    accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # harvest
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # tend()
    strategy.tend()

    # withdrawal
    vault.withdraw({"from": user})
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )

def test_emergency_exit(
    accounts, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # set emergency and exit
    strategy.setEmergencyExit()
    strategy.harvest()
    assert strategy.estimatedTotalAssets() < amount




def test_change_debt(
    gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()
    half = int(amount / 2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # In order to pass this tests, you will need to implement prepareReturn.
    # TODO: uncomment the following lines.
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half


def test_sweep(gov, vault, strategy, token, user, amount, weth, weth_amout, dai):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": user})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with brownie.reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with brownie.reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})

    # TODO: If you add protected tokens to the strategy.
    # Protected token doesn't work
    with brownie.reverts("!want"):
        strategy.sweep(token.address, {"from": gov})
    with brownie.reverts("!protected"):
        strategy.sweep(dai.address, {"from": gov})

    before_balance = weth.balanceOf(gov)
    weth.transfer(strategy, weth_amout, {"from": user})
    assert weth.address != strategy.want()
    assert weth.balanceOf(user) == 0
    strategy.sweep(weth, {"from": gov})
    assert weth.balanceOf(gov) == weth_amout + before_balance


def test_triggers(
    gov, vault, strategy, token, amount, user, weth, weth_amout, strategist
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    strategy.harvest()

    strategy.harvestTrigger(0)
    strategy.tendTrigger(0)


def sleepAndHarvest(times, strat, gov, vault, dai):
    for i in range(times):
        debugStratData(strat, "Before harvest" + str(i), vault, dai)
        chain.sleep(25000)
        chain.mine(100)
        strat.harvest({"from": gov})
        debugStratData(strat, "After harvest" + str(i), vault, dai)


# Used to debug strategy balance data
def debugStratData(strategy, msg, vault, dai):
    print(msg)
    print("Total assets " + str(strategy.estimatedTotalAssets()))
    print("88MPH Balance " + str(strategy.balanceOfWant()))
    print("DAI Balance " + str(dai.balanceOf(strategy.address)))
    print("Stake balance " + str(strategy.balanceOfStake()))
    print("Vault PPS " + str(vault.pricePerShare()))