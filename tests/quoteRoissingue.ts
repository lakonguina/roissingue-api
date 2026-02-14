import "dotenv/config";
import { createWalletClient, http, publicActions } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { base } from "viem/chains";
import { signQuoteSignablePayload } from "./signer";

const account = privateKeyToAccount(process.env.PK! as `0x${string}`);

const walletClient = createWalletClient({
  account,
  chain: base,
  transport: http(),
}).extend(publicActions);

interface QuoteResponse {
  payloadToSign: Array<{
    signablePayload?: unknown;
    metadata?: unknown;
    [key: string]: unknown;
  }>;
  quote: unknown;
  fee: unknown;
  quoteType: "simple" | "permit" | "onchain";
  ownerAddress: string;
  [key: string]: unknown;
}

async function main() {
  const res = await fetch("http://127.0.0.1:8001/v1/quote", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-KEY": "UHlWc_jdJGdoZCMzj7F1-VAaG7QihTjzMqfRjzyAZfM",
    },
    body: JSON.stringify({
      fromToken: {
        chainId: 8453,
        address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        amount: "100000",
      },
      toToken: {
        chainId: 8453,
        address: "0x4200000000000000000000000000000000000006",
      },
      feeToken: {
        chainId: 8453,
        address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      },
      fromAddress: account.address,
      toAddress: account.address,
    }),
  });

  if (!res.ok) throw new Error(`Quote failed: ${res.statusText}`);

  const quoteResponse = (await res.json()) as QuoteResponse;
  const { payloadToSign, quoteType } = quoteResponse;

  for (let i = 0; i < payloadToSign.length; i++) {
    const signature = await signQuoteSignablePayload(
      walletClient,
      quoteType,
      payloadToSign[i] as any,
    );
    payloadToSign[i] = { ...payloadToSign[i], signature };
  }

  const execRes = await fetch("http://127.0.0.1:8001/v1/execute", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-KEY": "UHlWc_jdJGdoZCMzj7F1-VAaG7QihTjzMqfRjzyAZfM",
    },
    body: JSON.stringify({ quote: quoteResponse, payloadToSign }),
  });

  if (!execRes.ok) throw new Error(`Execute failed: ${execRes.statusText}`);

  const result = await execRes.json();

  console.log("Supertx Hash:", result);
}

main().catch(console.error);
