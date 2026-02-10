"""SQLModel classes for blockchain transaction and user operation data structures."""

from typing import Any

from sqlmodel import SQLModel


class NativeTokenTransfer(SQLModel):
    """Represents a native token transfer between addresses on a blockchain."""

    fromAddress: str
    toAddress: str
    amount: str
    chainId: str


class ERC20TokenTransfer(SQLModel):
    """Represents an ERC20 token transfer with token metadata."""

    tokenAddress: str
    fromAddress: str
    toAddress: str
    amount: str
    name: str
    symbol: str
    decimals: int
    chainId: str


class AssetTransfers(SQLModel):
    """Container for native and ERC20 token transfers."""

    nativeTokenTransfers: list[NativeTokenTransfer] = []
    erc20TokenTransfers: list[ERC20TokenTransfer] = []


class StateTransitions(SQLModel):
    """Represents state transitions including asset transfers."""

    assetTransfers: AssetTransfers


class PaymentInfo(SQLModel):
    """Payment information for a user operation including gas and token details."""

    sender: str
    initCode: str
    nonce: str
    token: str
    chainId: str
    verificationGasLimit: str
    eoa: str
    shortEncoding: bool
    callGasLimit: str
    sponsored: bool
    tokenAmount: str
    tokenWeiAmount: str
    tokenValue: str
    gasFee: str
    orchestrationFee: str


class UserOp(SQLModel):
    """User operation data structure for ERC-4337 account abstraction."""

    sender: str
    nonce: str
    initCode: str
    callData: str
    accountGasLimits: str
    gasFees: str
    paymasterAndData: str
    preVerificationGas: str
    signature: str


class UserOpItem(SQLModel):
    """Complete user operation item with execution status and metadata."""

    userOp: UserOp
    userOpHash: str
    meeUserOpHash: str
    lowerBoundTimestamp: int
    upperBoundTimestamp: int
    maxGasLimit: str
    maxFeePerGas: str
    chainId: str
    shortEncoding: bool
    metadata: list[Any] = []
    stateTransitions: StateTransitions
    isCleanUpUserOp: bool | None = None
    simulationFinishedAt: int
    isConfirmed: bool
    executionStatus: str
    executionData: str
    actualGasCost: str
    revertError: str | None = None
    miningTimestamp: int
    minedTimestamp: int


class Trigger(SQLModel):
    """Trigger condition for a super transaction based on token amount and chain."""

    token: str
    amount: str
    chainId: str


class StatusResponse(SQLModel):
    """Complete super transaction details including payment info, user operations, and trigger."""

    itxHash: str
    node: str
    commitment: str
    paymentInfo: PaymentInfo
    userOps: list[UserOpItem]
    trigger: Trigger
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "itxHash": "0x42ffc9828c22a66b7a3185d4986356c704a09dc344a828379ca2e6b3acd81d54",
                    "node": "0x4b19129EA58431A06D01054f69AcAe5de50633b6",
                    "commitment": "0x188156c67fa485afec01ca5971a4a31c3e685d8fd918685527c18554a3d0624f40ee17954db6bd95ee1b2077ca294113c9c52f2b266d20ef7cfc0944dc5eb8701b",
                    "paymentInfo": {
                        "sender": "0xDc8fbe25200E4DB2277112FFB4Af9f3c7832dD68",
                        "initCode": "0x",
                        "nonce": "102639721097583983217535643021692796083602909243952289537519678420636210823168",
                        "token": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                        "chainId": "10",
                        "verificationGasLimit": "150000",
                        "eoa": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "shortEncoding": False,
                        "callGasLimit": "75000",
                        "sponsored": False,
                        "tokenAmount": "0.010246",
                        "tokenWeiAmount": "10246",
                        "tokenValue": "0.010246",
                        "gasFee": "0.000246",
                        "orchestrationFee": "0.010000",
                    },
                    "userOps": [],
                    "trigger": {
                        "token": "0x0000000000000000000000000b2c639c533813f4aa9d7837caf62653d097ff85",
                        "amount": "100000",
                        "chainId": "10",
                    },
                }
            ]
        }
    }
