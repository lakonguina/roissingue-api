async function main() {
  const LIFI_API_KEY = "";

  const q = {
    fromChain: "8453",
    toChain: "10",
    fromToken: "0x0000000000000000000000000000000000000000",
    toToken: "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58",
    fromAddress: "0x552008c0f6870c2f77e5cC1d2eb9bdff03e30Ea0",
    toAddress: "0x552008c0f6870c2f77e5cC1d2eb9bdff03e30Ea0",
    fromAmount: "100000000000000",
    slippage: "0.01",
  };

  const url = "https://li.quest/v1/quote?" + new URLSearchParams(q);

  const t0 = performance.now();
  const res = await fetch(url, {
    headers: { "x-lifi-api-key": LIFI_API_KEY },
  });
  const t1 = performance.now();

  console.log(`Quote latency: ${(t1 - t0).toFixed(0)}ms`);
}

main().catch(console.error);
