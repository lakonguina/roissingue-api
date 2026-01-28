from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlmodel import JSON, Field, SQLModel


class Fee(SQLModel, table=False):
    amount: str
    token: str
    chain_id: int = Field(..., alias="chainId")
    price_usd: Decimal = Field(..., alias="priceUsd")


class PaymentInfo(SQLModel, table=False):
    sender: str
    init_code: str = Field(..., alias="initCode")
    nonce: str
    token: str
    chain_id: int = Field(..., alias="chainId")
    verification_gas_limit: str = Field(..., alias="verificationGasLimit")
    eoa: str
    short_encoding: bool = Field(..., alias="shortEncoding")
    call_gas_limit: str = Field(..., alias="callGasLimit")
    sponsored: bool
    token_amount: str
    token_value: str
    token_wei_amount: str = Field(..., alias="tokenWeiAmount")
    gas_fee: str = Field(..., alias="gasFee")
    orchestration_fee: str = Field(..., alias="orchestrationFee")


class UserOpBase(SQLModel, table=False):
    sender: str
    nonce: str
    init_code: str = Field(..., alias="initCode")
    call_data: str = Field(..., alias="callData")
    call_gas_limit: str = Field(..., alias="callGasLimit")
    verification_gas_limit: str = Field(..., alias="verificationGasLimit")
    pre_verification_gas: str = Field(..., alias="preVerificationGas")
    max_fee_per_gas: str = Field(..., alias="maxFeePerGas")
    max_priority_fee_per_gas: str = Field(..., alias="maxPriorityFeePerGas")
    paymaster_and_data: str = Field(..., alias="paymasterAndData")


class MEEUserOperation(SQLModel, table=False):
    user_op: UserOpBase = Field(..., alias="userOp")
    user_op_hash: str = Field(..., alias="userOpHash")
    mee_user_op_hash: str = Field(..., alias="meeUserOpHash")
    lower_bound_timestamp: int = Field(..., alias="lowerBoundTimestamp")
    upper_bound_timestamp: int = Field(..., alias="upperBoundTimestamp")
    max_gas_limit: str = Field(..., alias="maxGasLimit")
    max_fee_per_gas: str = Field(..., alias="maxFeePerGas")
    chain_id: int = Field(..., alias="chainId")
    short_encoding: bool = Field(..., alias="shortEncoding")
    is_clean_up_user_op: Optional[bool] = Field(None, alias="isCleanUpUserOp")


class FundingToken(SQLModel, table=False):
    token_address: str = Field(..., alias="tokenAddress")
    chain_id: int = Field(..., alias="chainId")
    amount: str


class PermitDomain(SQLModel, table=False):
    name: str
    version: str
    chain_id: int = Field(..., alias="chainId")
    verifying_contract: str = Field(..., alias="verifyingContract")


class PermitMessage(SQLModel, table=False):
    owner: str
    spender: str
    value: str
    nonce: str
    deadline: str


class SignablePayload(SQLModel, table=False):
    domain: PermitDomain
    types: Dict[str, Any] = Field(..., sa_type=JSON)
    message: PermitMessage
    primary_type: str = Field(..., alias="primaryType")


class PermitMetadata(SQLModel, table=False):
    nonce: str
    name: str
    version: str
    domain_separator: str = Field(..., alias="domainSeparator")
    owner: str
    spender: str
    amount: str


class PayloadToSign(SQLModel, table=False):
    signable_payload: SignablePayload = Field(..., alias="signablePayload")
    metadata: PermitMetadata


class CallParam(SQLModel, table=False):
    param_type: int = Field(..., alias="paramType")
    fetcher_type: int = Field(..., alias="fetcherType")
    param_data: str = Field(..., alias="paramData")
    # constraints usually empty or very simple → keep as JSON
    constraints: List[Dict[str, Any]] = Field(default_factory=list, sa_type=JSON)


class CallInstruction(SQLModel, table=False):
    function_sig: str = Field(..., alias="functionSig")
    input_params: List[CallParam] = Field(..., alias="inputParams")
    output_params: List[Any] = Field(
        default_factory=list, alias="outputParams"
    )  # usually empty
    gas_limit: Optional[str] = Field(None, alias="gasLimit")


class InstructionBlock(SQLModel, table=False):
    calls: List[CallInstruction]
    chain_id: int = Field(..., alias="chainId")
    is_composable: bool = Field(..., alias="isComposable")


class ReturnedDataRouteStep(SQLModel, table=False):
    type: str
    protocol: str
    sources: List[Any] = Field(default_factory=list)
    src_token: str = Field(..., alias="srcToken")
    dst_token: str = Field(..., alias="dstToken")
    src_chain_id: int = Field(..., alias="srcChainId")
    dst_chain_id: int = Field(..., alias="dstChainId")
    input_amount: str = Field(..., alias="inputAmount")
    output_amount: str = Field(..., alias="outputAmount")
    min_output_amount: str = Field(..., alias="minOutputAmount")
    to_contract: str = Field(..., alias="toContract")
    call_data: str = Field(..., alias="callData")
    is_first_step: bool = Field(..., alias="isFirstStep")
    intermediate_tokens: List[str] = Field(
        default_factory=list, alias="intermediateTokens"
    )
    quote_id: Optional[str] = Field(None, alias="quoteId")


class ReturnedDataRoute(SQLModel, table=False):
    summary: str
    steps: List[ReturnedDataRouteStep]
    total_gas_fees_usd: Decimal = Field(..., alias="totalGasFeesUsd")
    total_bridge_fees_usd: Decimal = Field(..., alias="totalBridgeFeesUsd")
    estimated_time: int = Field(..., alias="estimatedTime")
    output_amount: str = Field(..., alias="outputAmount")
    min_output_amount: str = Field(..., alias="minOutputAmount")
    type: str
    intermediate_tokens: List[str] = Field(
        default_factory=list, alias="intermediateTokens"
    )


class ReturnedDataItem(SQLModel, table=False):
    instructions: List[InstructionBlock]
    output_amount: Optional[str] = None
    min_output_amount: Optional[str] = None
    route: Optional[ReturnedDataRoute] = None
    intermediate_tokens: List[str] = Field(default_factory=list)
    output_amount_usd: Optional[Decimal] = Field(None, alias="outputAmountUsd")
    min_output_amount_usd: Optional[Decimal] = Field(None, alias="minOutputAmountUsd")


class QuoteResponse(SQLModel, table=True):
    __tablename__ = "quote_responses"

    id: Optional[int] = Field(default=None, primary_key=True)

    owner_address: str = Field(..., index=True, alias="ownerAddress")
    fee: Fee

    quote_type: str = Field(..., alias="quoteType")

    quote_hash: str = Field(..., alias="quote.hash")
    node: str
    commitment: str

    payment_info: PaymentInfo = Field(..., alias="quote.paymentInfo")
    user_ops: List[MEEUserOperation] = Field(..., alias="quote.userOps")
    funding_tokens: List[FundingToken] = Field(..., alias="quote.fundingTokens")

    payload_to_sign: List[PayloadToSign] = Field(..., alias="payloadToSign")

    instructions: List[InstructionBlock] = Field(..., sa_type=JSON)
    returned_data: List[ReturnedDataItem] = Field(
        ..., alias="returnedData", sa_type=JSON
    )

    # Optional metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_response: Optional[Dict[str, Any]] = Field(
        None, sa_type=JSON
    )  # full original if needed
