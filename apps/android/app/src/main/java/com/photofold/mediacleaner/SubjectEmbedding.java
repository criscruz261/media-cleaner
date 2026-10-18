package com.photofold.mediacleaner;

import android.content.Context;
import android.graphics.Bitmap;
import com.google.mediapipe.framework.image.BitmapImageBuilder;
import com.google.mediapipe.framework.image.MPImage;
import com.google.mediapipe.tasks.core.BaseOptions;
import com.google.mediapipe.tasks.vision.imageembedder.ImageEmbedder;

/** Bundled CPU model; no network calls and no identity recognition. */
final class SubjectEmbedding {
  record Features(byte[] whole, byte[][] regions) {}

  private static ImageEmbedder embedder;

  private static byte[] embed(Bitmap bitmap) {
    try (MPImage image =
        new BitmapImageBuilder(bitmap.copy(Bitmap.Config.ARGB_8888, false)).build()) {
      float[] vector = embedder.embed(image).embeddingResult().embeddings().get(0).floatEmbedding();
      byte[] result = new byte[vector.length];
      for (int i = 0; i < vector.length; i++)
        result[i] = (byte) Math.round(Math.max(-1, Math.min(1, vector[i])) * 127);
      return result;
    }
  }

  static synchronized Features describe(Context context, Bitmap bitmap) {
    if (embedder == null)
      embedder =
          ImageEmbedder.createFromOptions(
              context.getApplicationContext(),
              ImageEmbedder.ImageEmbedderOptions.builder()
                  .setBaseOptions(
                      BaseOptions.builder().setModelAssetPath("subject_embedder.tflite").build())
                  .setL2Normalize(true)
                  .build());
    byte[] whole = embed(bitmap);
    byte[][] regions = new byte[4][];
    int width = bitmap.getWidth(), height = bitmap.getHeight();
    if (Math.min(width, height) < 2) return new Features(whole, new byte[0][]);
    for (int y = 0; y < 2; y++)
      for (int x = 0; x < 2; x++) {
        int left = x * width / 2, top = y * height / 2;
        Bitmap region =
            Bitmap.createBitmap(
                bitmap, left, top, (x + 1) * width / 2 - left, (y + 1) * height / 2 - top);
        try {
          regions[y * 2 + x] = embed(region);
        } finally {
          if (region != bitmap) region.recycle();
        }
      }
    return new Features(whole, regions);
  }
}
