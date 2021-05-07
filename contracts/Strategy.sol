// SPDX-License-Identifier: AGPL-3.0
// Feel free to change the license, but this is what we use

// Feel free to change this version of Solidity. We support >=0.6.0 <0.7.0;
pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

// These are the core Yearn libraries
import {
    BaseStrategy,
    StrategyParams
} from "@yearnvaults/contracts/BaseStrategy.sol";
import {
    SafeERC20,
    SafeMath,
    IERC20,
    Address
} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";
import {Math} from "@openzeppelin/contracts/math/Math.sol";

interface I_88MPHStaking {
    function stake(uint256 amount) external;

    function withdraw(uint256 amount) external;

    function exit() external;

    function getReward() external;

    function rewards(address account) external view returns (uint256);

    function rewardPerToken() external view returns (uint256);

    function balanceOf(address account) external view returns (uint256);
}

// Part: IUni

interface IUni{
    function getAmountsOut(
        uint256 amountIn,
        address[] calldata path
    ) external view returns (uint256[] memory amounts);

    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);
}

// File: Strategy.sol

contract Strategy is BaseStrategy {
    using SafeERC20 for IERC20;
    using Address for address;
    using SafeMath for uint256;

    //Initiate 88mph interface
    I_88MPHStaking public I88 = I_88MPHStaking(0x98df8D9E56b51e4Ea8AA9b57F8A5Df7A044234e1);
    IERC20 public MPH = IERC20(0x8888801aF4d980682e47f1A9036e589479e835C5);
    IERC20 public DAI = IERC20(0x6B175474E89094C44Da98b954EedeAC495271d0F);
    address public constant weth = address(0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2);
    address public constant uniswapRouter = address(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
    uint256 public minDaiToSell = 0.1 ether;


    constructor(address _vault) public BaseStrategy(_vault) {
        //Approve staking contract to spend 88MPH tokens
        want.safeApprove(address(I88), type(uint256).max);
        IERC20(DAI).safeApprove(uniswapRouter, type(uint256).max);
    }

    function name() external view override returns (string memory) {
        return "Strategy88MPHStaking";
    }

    /**
     * @notice return the idle want in the strategy
     * @return amount of want available in the strategy
     */
    function balanceOfWant() public view returns (uint256) {
        return want.balanceOf(address(this));
    }

    /**
     * @notice return the deployed want in the 88MPH strategy
     * @return amount of want deployed to staking
     */
    function balanceOfStake() public view returns (uint256) {
        return I88.balanceOf(address(this));
    }

    /**
     * @notice return the rewards the strategy is eligible for in DAI
     * @return amount of DAI the strategy can receive
     */
    function pendingReward() public view returns (uint256) {
        return I88.rewards(address(this));
    }

    /**
     * @notice return the estimated amount that the strategy has access to
     * @return amount of MPH the strategy controls
     */
    function estimatedTotalAssets() public view override returns (uint256) {
        //Add the vault tokens + staked tokens from 88MPH staking
        uint256 balanceOfStake = balanceOfStake();
        uint256 _claimableDai = pendingReward();
        uint256 currentDai = DAI.balanceOf(address(this));

        // Use touch price. it doesnt matter if we are wrong as this is not used for decision making
        uint256 estimatedWant =  priceCheck(address(DAI), address(MPH),_claimableDai.add(currentDai));
        uint256 conservativeWant = estimatedWant.mul(9).div(10); //10% pessimist
        return balanceOfWant().add(balanceOfStake).add(conservativeWant);
    }

    /**
     * @notice return the estimated amount that the strategy has access to
     * @param _debtOutstanding the funds that are owed from the strategy to the vault
     * @return _profit the profit the strategy has gained
     * @return _loss the loss of the strategy, only necessary if debtOutstanding > 0
     * @return _debtPayment the amount to send to the vault, only necessary if debtOutstanding > 0
     */
    function prepareReturn(uint256 _debtOutstanding)
        internal
        override
        returns (
            uint256 _profit,
            uint256 _loss,
            uint256 _debtPayment
        )
    {
        // We might need to return want to the vault
        if (_debtOutstanding > 0) {
            uint256 _amountFreed = 0;
            (_amountFreed, _loss) = liquidatePosition(_debtOutstanding);
            _debtPayment = Math.min(_amountFreed, _debtOutstanding);
        }

        uint256 balanceOfWantBefore = balanceOfWant();
        I88.getReward();
        _disposeOfDai();

        _profit = balanceOfWant().sub(balanceOfWantBefore);
    }

    /**
     * @notice execute the 'fund to work' part of the strategy (stake in 88MPH)
     * @param _debtOutstanding the funds that are owed from the strategy to the vault
     */
    function adjustPosition(uint256 _debtOutstanding) internal override {
        uint256 _wantAvailable = balanceOfWant();

        if (_debtOutstanding >= _wantAvailable) {
            return;
        }

        uint256 toInvest = _wantAvailable.sub(_debtOutstanding);

        if (toInvest > 0) {
            I88.stake(toInvest);
        }
    }

    /**
     * @notice remove a certain amount of funds from deployment in the strategy
     * @param _amountNeeded the funds that are owed from the strategy to the vault
     * @return _liquidatedAmount the amount of funds to remove from staking
     * @return _loss the loss of the strategy
     */
    function liquidatePosition(uint256 _amountNeeded) internal override returns (uint256 _liquidatedAmount, uint256 _loss) {
        // NOTE: Maintain invariant `want.balanceOf(this) >= _liquidatedAmount`
        // NOTE: Maintain invariant `_liquidatedAmount + _loss <= _amountNeeded`
        uint256 balanceWant = balanceOfWant();
        uint256 balanceStaked = balanceOfStake();
        if (_amountNeeded > balanceWant) {
            // unstake needed amount
            I88.withdraw((Math.min(balanceStaked, _amountNeeded - balanceWant)));
        }
        // Since we might free more than needed, let's send back the min
        _liquidatedAmount = Math.min(balanceOfWant(), _amountNeeded);
    }

    /**
     * @notice liquidate all positions to want
     * @param _newStrategy the address of the strategy for migration
     */
    function prepareMigration(address _newStrategy) internal override {
        // If we have pending rewards,take that out
        I88.exit();
        _disposeOfDai();
    }

    /**
     * @notice the addresses of funds that cant be acquired from sweep
     * @dev Override this to add all tokens/tokenized positions this contract manages
     * on a *persistent* basis (e.g. not just for swapping back to want ephemerally)
     * @return the addresses of the protected tokens
     */
    function protectedTokens() internal view override returns (address[] memory) {
        address[] memory protected = new address[](2);
        protected[0] = address(I88); // Staked 88MPH tokens from governance contract
        protected[1] = address(DAI); // DAI is held in the contract at points
        return protected;
    }

    /**
     * @notice check the conversion price of dai to mph
     * @dev WARNING manipulatable and simple routing. Only use for safe functions
     * @param start the start of the path (dai)
     * @param end the end of the path (mph)
     * @param _amount the amount being checked of dai
     * @return amount you would receive for this trade (the price)
     */
    function priceCheck(address start, address end, uint256 _amount) public view returns (uint256) {
        if (_amount == 0) {
            return 0;
        }
        address[] memory path;
        if(start == weth){
            path = new address[](2);
            path[0] = weth;
            path[1] = end;
        }else{
            path = new address[](3);
            path[0] = start;
            path[1] = weth;
            path[2] = end;
        }

        uint256[] memory amounts = IUni(uniswapRouter).getAmountsOut(_amount, path);

        return amounts[amounts.length - 1];
    }

    /**
     * @notice remove all dai from the contract and convert it to MPH
     */
    function _disposeOfDai() internal {
        uint256 _dai = DAI.balanceOf(address(this));
        // if there is not enough dai, dont do this.
        if (_dai > minDaiToSell) {
            address[] memory path = new address[](3);
            path[0] = address(DAI);
            path[1] = weth;
            path[2] = address(want);

            IUni(uniswapRouter).swapExactTokensForTokens(_dai, uint256(0), path, address(this), now);
        }
    }
}
