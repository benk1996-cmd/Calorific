// Client-side resize + re-encode. Drawing to a canvas strips EXIF/GPS metadata.
export const MAX_DIM = 1280;
export const MAX_BYTES = 1_000_000;

export function fitDimensions(w: number, h: number, max = MAX_DIM): { width: number; height: number } {
  const scale = Math.min(1, max / Math.max(w, h));
  return { width: Math.max(1, Math.round(w * scale)), height: Math.max(1, Math.round(h * scale)) };
}

/** Quality, then dimension-scale steps to try until the blob fits under maxBytes. */
export function attempts(): { quality: number; scale: number }[] {
  const out: { quality: number; scale: number }[] = [];
  for (const scale of [1, 0.8, 0.6]) for (const quality of [0.85, 0.7, 0.55]) out.push({ quality, scale });
  return out;
}

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error("Encode failed"))), "image/jpeg", quality));
}

export async function resizeToJpeg(file: File, maxBytes = MAX_BYTES): Promise<Blob> {
  const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  const { width, height } = fitDimensions(bmp.width, bmp.height);
  let last: Blob | null = null;
  for (const { quality, scale } of attempts()) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    canvas.getContext("2d")!.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    last = await toBlob(canvas, quality);
    if (last.size <= maxBytes) break;
  }
  bmp.close();
  return last!;
}
