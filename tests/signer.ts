import "dotenv/config";
import {
  Address,
  createWalletClient,
  Hex,
  http,
  publicActions,
  SignTypedDataParameters,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { base } from "viem/chains";

type SignableTypedDataPayload = Omit<SignTypedDataParameters, "account">;

type SignablePersonalMessagePayload = {
  message: { raw: Hex };
};

type SignableSimplePayload =
  | SignableTypedDataPayload
  | SignablePersonalMessagePayload;

type SignableOnChainPayload = {
  data: Hex;
  to: Address;
  chainId: number;
  value?: string | number | bigint;
};

function isTypedDataPayload(
  payload: SignableSimplePayload,
): payload is SignableTypedDataPayload {
  return "domain" in payload && "primaryType" in payload;
}

const eoaAccount = privateKeyToAccount(process.env.PK! as `0x${string}`);

const walletClient = createWalletClient({
  account: eoaAccount,
  chain: base,
  transport: http(),
}).extend(publicActions);

async function signSimple(signable: SignableSimplePayload): Promise<Hex> {
  if (isTypedDataPayload(signable)) {
    return walletClient.signTypedData({
      ...signable,
      account: eoaAccount,
    });
  }
  return eoaAccount.signMessage(signable);
}

async function signPermit(typedData: SignableTypedDataPayload): Promise<Hex> {
  return walletClient.signTypedData({
    ...typedData,
    account: eoaAccount,
  });
}

async function signOnChain(tx: SignableOnChainPayload): Promise<Hex> {
  const hash = await walletClient.sendTransaction({
    to: tx.to,
    data: tx.data,
    value: tx.value !== undefined ? BigInt(tx.value) : 0n,
  });
  await walletClient.waitForTransactionReceipt({ hash, confirmations: 5 });
  return hash;
}

type SimpleQuotePayload = {
  signablePayload: SignableSimplePayload;
  metadata?: unknown;
};

type PermitQuotePayload = {
  signablePayload: SignableTypedDataPayload;
  metadata: unknown;
};

type OnChainQuotePayload = SignableOnChainPayload;

type QuotePayloadToSign =
  | SimpleQuotePayload
  | PermitQuotePayload
  | OnChainQuotePayload;

export async function signQuoteSignablePayload(
  quoteType: string,
  payload: QuotePayloadToSign | any,
): Promise<Hex> {
  switch (quoteType.toLowerCase()) {
    case "simple": {
      if (!("signablePayload" in payload)) {
        throw new Error("simple quote: signablePayload manquant");
      }
      return signSimple(payload.signablePayload);
    }

    case "permit": {
      if (!("signablePayload" in payload)) {
        throw new Error("permit quote: signablePayload manquant");
      }
      const sp = payload.signablePayload;
      if (!("domain" in sp && "types" in sp && "primaryType" in sp)) {
        throw new Error("permit: payload n'est pas du EIP-712 valide");
      }
      return signPermit(sp as SignableTypedDataPayload);
    }

    case "onchain": {
      if ("signablePayload" in payload) {
        throw new Error("onchain quote: ne doit PAS contenir signablePayload");
      }
      if (!("to" in payload && "data" in payload && "chainId" in payload)) {
        throw new Error("onchain: to/data/chainId manquants");
      }
      return signOnChain(payload as SignableOnChainPayload);
    }

    default:
      throw new Error(`quoteType non supporté : ${quoteType}`);
  }
}
