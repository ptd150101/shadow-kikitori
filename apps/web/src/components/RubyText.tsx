import type { FuriganaToken } from "../types/api";

export default function RubyText({ tokens, fallback, className }: { tokens?: FuriganaToken[] | null; fallback?: string | null; className?: string }) {
  if (!tokens?.length) return <span className={className}>{fallback ?? ""}</span>;
  return <span className={className ?? "ruby"}>
    {tokens.map((token, index) => token.ruby && token.reading ? (
      <ruby key={`${token.surface}-${index}`}>{token.surface}<rt>{token.reading}</rt></ruby>
    ) : <span key={`${token.surface}-${index}`}>{token.surface}</span>)}
  </span>;
}
