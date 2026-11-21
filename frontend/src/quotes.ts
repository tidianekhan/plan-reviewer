// Find where a quote sits in the plan, using the contract's rule: runs of whitespace count as one space.
export function locateQuote(plan: string, quote: string): [number, number] | null {
  const chars: string[] = [];
  const index: number[] = [];
  for (let i = 0; i < plan.length; i++) {
    const ch = plan[i];
    if (/\s/.test(ch)) {
      if (chars.length && chars[chars.length - 1] === ' ') continue;
      chars.push(' ');
    } else {
      chars.push(ch);
    }
    index.push(i);
  }
  const needle = quote.replace(/\s+/g, ' ').trim();
  if (!needle) return null;
  const at = chars.join('').indexOf(needle);
  if (at < 0) return null;
  return [index[at], index[at + needle.length - 1] + 1];
}
