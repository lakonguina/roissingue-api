import { createWalletClient, http, parseUnits } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { base } from "viem/chains";

const account = privateKeyToAccount(
  "0x...",
);

const walletClient = createWalletClient({
  account,
  chain: base,
  transport: http(),
});

async function main() {
  // Step 1: Build quote request with intent-simple in composeFlows
  const quoteRequest = {
    mode: "eoa",
    ownerAddress: account.address,
    simulating: false,
    fundingTokens: [
      {
        tokenAddress: "0x0000000000000000000000000000000000000000", // ETH on Base
        chainId: 8453,
        amount: "100000000000000",
      },
    ],
    feeToken: {
      address: "0x0000000000000000000000000000000000000000",
      chainId: 8453,
    },
    composeFlows: [
      // Cross-chain swap: USDC (Base) → USDT (OP)
      {
        type: "/instructions/intent-simple",
        data: {
          srcChainId: 8453,
          dstChainId: 8453,
          srcToken: "0x0000000000000000000000000000000000000000",
          dstToken: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
          amount: "100000000000000",
          slippage: 0.01,
          routeSelectionMode: "fast-quote",
        },
      },
      // Withdraw USDT to EOA (critical for EOA mode)
      {
        type: "/instructions/build",
        data: {
          functionSignature: "function transfer(address to, uint256 value)",
          args: [
            account.address,
            {
              type: "runtimeErc20Balance",
              tokenAddress: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
              constraints: { gte: "1" },
            },
          ],
          to: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
          chainId: 8453,
        },
      },
    ],
  };

  // Step 2: Get quote
  const t0 = performance.now();
  const quote = await fetch("https://api.biconomy.io/v1/quote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(quoteRequest),
  }).then((r) => r.json());
  const t1 = performance.now();
  console.log(`Quote latency: ${(t1 - t0).toFixed(0)}ms`);
}

main().catch(console.error);
