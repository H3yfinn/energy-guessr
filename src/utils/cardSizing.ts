export type CardSizing = {
  span: number;
  minWidth: number;
};

export function computeCardSizing(
  _barCount: number,
  _sectorKey: string
): CardSizing {
  // Keep every chart the same nominal size and rely on auto-fit wrapping.
  return { span: 1, minWidth: 280 };
}
