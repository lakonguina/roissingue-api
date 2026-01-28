import { Address, Hex, SignTypedDataParameters } from "viem";

/**
 * Types for different signable payloads.
 */

// Payload for EIP-712 typed data signature (smart-account v2.2.1, permits)
type SignableTypedDataPayload = Omit<SignTypedDataParameters, "account">;

// Payload for personal message signing (legacy v2.1.0, eoa-7702)
type SignablePersonalMessagePayload = {
  message: {
    raw: Hex;
  };
};

// Union type for "simple" quote type payloads (can be either format)
type SignableSimplePayload =
  | SignableTypedDataPayload
  | SignablePersonalMessagePayload;

// Payload for on-chain transaction signing
type SignableOnChainPayload =
  | {
      data: Hex;
      to: Address;
      chainId: number;
      value: string;
    }
  | {
      data: Hex;
      to: Address;
      chainId: number;
      value?: string | undefined;
    };

/**
 * Type guard to detect EIP-712 typed data payload.
 * v2.2.1 smart accounts use typed data, v2.1.0 uses personal message.
 */
function isTypedDataPayload(
  payload: SignableSimplePayload,
): payload is SignableTypedDataPayload {
  return "domain" in payload && "primaryType" in payload;
}

/**
 * Signs a "simple" quote payload. Handles both formats:
 * - EIP-712 typed data (v2.2.1 smart accounts)
 * - Personal message (v2.1.0 legacy accounts, eoa-7702)
 *
 * @param walletClient - The viem wallet client to use for signing.
 * @param signablePayload - The payload to sign (auto-detected format).
 * @returns The signature as a Hex string.
 *
 * @example
 * // EIP-712 typed data (v2.2.1 smart account)
 * const signature = await signSimpleQuoteSignablePayload(walletClient, {
 *   domain: { name: "Nexus" },
 *   types: { MeeUserOp: [...], SuperTx: [{ name: "meeUserOps", type: "MeeUserOp[]" }] },
 *   primaryType: "SuperTx",
 *   message: { meeUserOps: [{ userOpHash: "0x...", lowerBoundTimestamp: 0, upperBoundTimestamp: 1765465749 }] }
 * });
 *
 * @example
 * // Personal message (v2.1.0 or eoa-7702)
 * const signature = await signSimpleQuoteSignablePayload(walletClient, {
 *   message: { raw: "0x68656c6c6f" }
 * });
 */
const signSimpleQuoteSignablePayload = async (
  walletClient: any,
  signablePayload: SignableSimplePayload,
): Promise<Hex> => {
  if (isTypedDataPayload(signablePayload)) {
    return await walletClient.signTypedData(signablePayload);
  } else {
    return await walletClient.signMessage(signablePayload);
  }
};

/**
 * Signs a permit quote payload (EIP-712 typed data for ERC20 permits).
 *
 * @param walletClient - The viem wallet client to use for signing.
 * @param signablePayload - The EIP-712 payload to sign.
 * @returns The signature as a Hex string.
 *
 * @example
 * const signature = await signPermitQuoteSignablePayload(walletClient, {
 *   domain: { ... },
 *   types: { ... },
 *   primaryType: "Permit",
 *   message: { ... }
 * });
 */
const signPermitQuoteSignablePayload = async (
  walletClient: any,
  signablePayload: SignableTypedDataPayload,
): Promise<Hex> => {
  return await walletClient.signTypedData(signablePayload);
};

/**
 * Signs an on-chain quote payload (transaction).
 *
 * @param walletClient - The viem wallet client to use for signing.
 * @param signablePayload - The transaction payload to send.
 * @returns The transaction hash as a Hex string.
 *
 * @example
 * const txHash = await signOnChainQuoteSignablePayload(walletClient, {
 *   to: "0x...",
 *   data: "0x...",
 *   value: "0",
 *   chainId: 1
 * });
 */
const signOnChainQuoteSignablePayload = async (
  walletClient: any,
  signablePayload: SignableOnChainPayload,
): Promise<Hex> => {
  const hash = await walletClient.sendTransaction({
    account: walletClient.account,
    to: signablePayload.to,
    data: signablePayload.data,
    value: BigInt(signablePayload.value || "0"),
  });
  await walletClient.waitForTransactionReceipt({ hash, confirmations: 5 });
  return hash;
};

/**
 * Union type for all supported payloads to sign.
 */
type PayloadToSign =
  | {
      signablePayload: SignableSimplePayload;
      metadata?: any;
    }
  | {
      signablePayload: SignableTypedDataPayload;
      metadata: {
        nonce: string;
        name: string;
        version: string;
        domainSeparator: string;
        owner: string;
        spender: string;
        amount: string;
      };
    }
  | SignableOnChainPayload;

/**
 * Signs a quote payload based on its type.
 * Automatically handles both EIP-712 and personal message formats for "simple" type.
 *
 * @param walletClient - The viem wallet client to use for signing.
 * @param quoteType - The type of quote from the API response.
 * @param payloadToSign - The payload to sign.
 * @returns The signature or transaction hash as a Hex string.
 *
 * @example
 * // Simple - EIP-712 (v2.2.1 smart account)
 * const sig = await signQuoteSignablePayload(walletClient, "simple", {
 *   signablePayload: { domain: { name: "Nexus" }, types: {...}, primaryType: "SuperTx", message: { meeUserOps: [...] } }
 * });
 *
 * @example
 * // Simple - Personal message (v2.1.0 or eoa-7702)
 * const sig = await signQuoteSignablePayload(walletClient, "simple", {
 *   signablePayload: { message: { raw: "0x68656c6c6f" } }
 * });
 *
 * @example
 * // Permit (EIP-712 for ERC20)
 * const sig = await signQuoteSignablePayload(walletClient, "permit", {
 *   signablePayload: { domain: {...}, types: {...}, primaryType: "Permit", message: {...} },
 *   metadata: { ... }
 * });
 *
 * @example
 * // On-chain transaction
 * const txHash = await signQuoteSignablePayload(walletClient, "onchain", {
 *   to: "0x...",
 *   data: "0x...",
 *   value: "0",
 *   chainId: 1
 * });
 */
export const signQuoteSignablePayload = async (
  walletClient: any,
  quoteType: string,
  payloadToSign: any,
): Promise<Hex> => {
  switch (quoteType) {
    case "simple":
      if ("signablePayload" in payloadToSign) {
        return await signSimpleQuoteSignablePayload(
          walletClient,
          payloadToSign.signablePayload,
        );
      }
      return await signSimpleQuoteSignablePayload(walletClient, payloadToSign);
    case "permit":
      if (!("signablePayload" in payloadToSign)) {
        throw new Error("Permit requires signablePayload");
      }
      return await signPermitQuoteSignablePayload(
        walletClient,
        payloadToSign.signablePayload,
      );
    case "onchain":
      return await signOnChainQuoteSignablePayload(walletClient, payloadToSign);
    default:
      throw new Error("Unsupported quote type, can't sign the payload");
  }
};

export {
  signSimpleQuoteSignablePayload,
  signPermitQuoteSignablePayload,
  signOnChainQuoteSignablePayload,
};

export type {
  SignableTypedDataPayload,
  SignablePersonalMessagePayload,
  SignableSimplePayload,
  SignableOnChainPayload,
  PayloadToSign,
};
