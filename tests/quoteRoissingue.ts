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
  const res = await fetch("http://127.0.0.1:8000/v1/quote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      fromToken: {
        chainId: 10,
        address: "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        amount: "100000",
      },
      toToken: { slug: "wrapped-ethereum" },
      feeToken: {
        chainId: 10,
        address: "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
      },
      allowChains: [10, 8453],
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

  const execRes = await fetch("http://127.0.0.1:8000/v1/execute", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quote: quoteResponse, payloadToSign }),
  });

  if (!execRes.ok) throw new Error(`Execute failed: ${execRes.statusText}`);

  const result = await execRes.json();

  console.log("Supertx Hash:", result.supertxHash);

  // TODO: Await like 5 seconds
  const getStatus = await fetch("http://127.0.0.1:8000/v1/status/", {
    method: "GET",
  });

  // TODO: Refetch to get the status
}

main().catch(console.error);
