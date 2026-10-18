package com.photofold.mediacleaner;

import android.content.*;
import android.database.Cursor;
import android.graphics.*;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import com.photofold.matching.Matcher;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

final class MediaRepository {
  interface Check {
    void run();
  }

  interface Progress {
    void update(String text);
  }

  private static final String[] COLUMNS = {
    "_id",
    "_display_name",
    "_size",
    "date_modified",
    "generation_modified",
    "mime_type",
    "relative_path",
    "is_trashed",
    "is_pending"
  };

  static List<Media> discover(Context context, String album, Check check) {
    List<Media> result = new ArrayList<>();
    for (boolean video : new boolean[] {false, true}) {
      Uri collection =
          video
              ? MediaStore.Video.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
              : MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL);
      String[] columns = Arrays.copyOf(COLUMNS, COLUMNS.length + 1);
      columns[COLUMNS.length] = "volume_name";
      String where = "is_trashed=0 AND is_pending=0 AND _size>0";
      try (Cursor cursor =
          context
              .getContentResolver()
              .query(collection, columns, where, null, "_display_name ASC, _id ASC")) {
        if (cursor == null) continue;
        while (cursor.moveToNext()) {
          check.run();
          String volume = cursor.getString(cursor.getColumnIndexOrThrow("volume_name"));
          Uri base =
              video
                  ? MediaStore.Video.Media.getContentUri(volume)
                  : MediaStore.Images.Media.getContentUri(volume);
          Uri uri =
              ContentUris.withAppendedId(base, cursor.getLong(cursor.getColumnIndexOrThrow("_id")));
          Media media = read(cursor, uri);
          if (album.isEmpty() || album.equals(media.album)) result.add(media);
        }
      } catch (SecurityException denied) {
        /* Android may grant access to only one media type. */
      }
    }
    Map<String, Set<String>> companions = new HashMap<>();
    for (Media media : result)
      companions.computeIfAbsent(stem(media), ignored -> new HashSet<>()).add(media.kind);
    for (Media media : result) {
      String lower = media.name.toLowerCase(Locale.ROOT);
      if (lower.matches(".*\\.(dng|cr2|cr3|nef|arw|orf|rw2|raf|pef|srw|3fr|rwl)$"))
        media.protection = "RAW original protected";
      else if (companions.get(stem(media)).size() > 1)
        media.protection = "Possible photo/video companion protected";
    }
    result.sort(Comparator.comparing((Media m) -> m.name).thenComparing(m -> m.uri));
    return result;
  }

  private static String stem(Media media) {
    int dot = media.name.lastIndexOf('.');
    return media.album.toLowerCase(Locale.ROOT)
        + "/"
        + (dot < 0 ? media.name : media.name.substring(0, dot)).toLowerCase(Locale.ROOT);
  }

  private static Media read(Cursor c, Uri uri) {
    Media media = new Media();
    media.uri = uri.toString();
    media.name = c.getString(c.getColumnIndexOrThrow("_display_name"));
    if (media.name == null) media.name = "Unnamed media";
    media.size = c.getLong(c.getColumnIndexOrThrow("_size"));
    media.mime = c.getString(c.getColumnIndexOrThrow("mime_type"));
    if (media.mime == null) media.mime = "application/octet-stream";
    media.kind = media.mime.startsWith("video/") ? "video" : "image";
    media.album = c.getString(c.getColumnIndexOrThrow("relative_path"));
    if (media.album == null) media.album = "";
    media.identity =
        media.uri
            + "|"
            + media.size
            + "|"
            + c.getLong(c.getColumnIndexOrThrow("date_modified"))
            + "|"
            + c.getLong(c.getColumnIndexOrThrow("generation_modified"));
    return media;
  }

  static boolean unchanged(Context context, Media media) {
    Bundle query = new Bundle();
    query.putInt(MediaStore.QUERY_ARG_MATCH_TRASHED, MediaStore.MATCH_INCLUDE);
    try (Cursor c = context.getContentResolver().query(media.uri(), COLUMNS, query, null)) {
      return c != null
          && c.moveToFirst()
          && c.getInt(c.getColumnIndexOrThrow("is_trashed")) == 0
          && c.getInt(c.getColumnIndexOrThrow("is_pending")) == 0
          && read(c, media.uri()).identity.equals(media.identity);
    }
  }

  static String hash(Context context, Media media, Check check, Progress progress)
      throws Exception {
    if (!unchanged(context, media))
      throw new IOException("Media changed or is no longer accessible");
    MessageDigest sha = MessageDigest.getInstance("SHA-256");
    long read = 0;
    try (InputStream source = context.getContentResolver().openInputStream(media.uri())) {
      if (source == null) throw new IOException("Media stream unavailable");
      byte[] buffer = new byte[1024 * 1024];
      int count;
      while ((count = source.read(buffer)) != -1) {
        check.run();
        sha.update(buffer, 0, count);
        read += count;
        progress.update(
            "Reading "
                + media.name
                + " · "
                + (read / 1048576)
                + " / "
                + Math.max(1, media.size / 1048576)
                + " MB");
      }
    }
    if (read != media.size || !unchanged(context, media))
      throw new IOException("Media changed while reading");
    StringBuilder result = new StringBuilder();
    for (byte b : sha.digest()) result.append(String.format(Locale.ROOT, "%02x", b & 255));
    return result.toString();
  }

  static Matcher.Signature signature(Context context, Bitmap source) {
    Bitmap square = Bitmap.createScaledBitmap(source, 32, 32, true),
        gradient = Bitmap.createScaledBitmap(source, 9, 8, true);
    try {
      int[] a = new int[1024], b = new int[72];
      square.getPixels(a, 0, 32, 0, 0, 32, 32);
      gradient.getPixels(b, 0, 9, 0, 0, 9, 8);
      Matcher.Signature classic =
          Matcher.fingerprint(a, b, (double) source.getWidth() / source.getHeight());
      if (classic == null) return null;
      SubjectEmbedding.Features features = SubjectEmbedding.describe(context, source);
      return new Matcher.Signature(
          classic.phash(),
          classic.dhash(),
          classic.aspect(),
          classic.red(),
          classic.green(),
          classic.blue(),
          features.whole(),
          features.regions());
    } finally {
      if (square != source) square.recycle();
      if (gradient != source && gradient != square) gradient.recycle();
    }
  }

  static String describe(
      Context context, Media media, Check check, Progress progress, int sampleCount)
      throws Exception {
    JSONObject result =
        new JSONObject().put("version", Matcher.VERSION).put("sample_count", sampleCount);
    if (media.kind.equals("video")) {
      try (MediaMetadataRetriever retriever = new MediaMetadataRetriever()) {
        retriever.setDataSource(context, media.uri());
        String durationText =
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
        double duration = durationText == null ? 0 : Double.parseDouble(durationText) / 1000;
        if (duration <= 0 || !Double.isFinite(duration))
          throw new IOException("Video duration unavailable");
        JSONArray frames = new JSONArray();
        for (int slot = 0; slot < sampleCount; slot++) {
          check.run();
          progress.update(
              "Comparing " + media.name + " · sample " + (slot + 1) + " / " + sampleCount);
          Bitmap frame =
              retriever.getScaledFrameAtTime(
                  (long) (duration * (slot + 0.5) / sampleCount * 1_000_000),
                  MediaMetadataRetriever.OPTION_CLOSEST,
                  256,
                  256);
          if (frame != null)
            try {
              Matcher.Signature signature = signature(context, frame);
              if (signature != null) frames.put(Media.json(signature).put("slot", slot));
            } finally {
              frame.recycle();
            }
        }
        result.put("duration", duration).put("frames", frames);
        Media temporary = new Media();
        temporary.uri = media.uri;
        temporary.name = media.name;
        temporary.size = media.size;
        temporary.digest = media.digest;
        temporary.kind = media.kind;
        temporary.descriptor = result.toString();
        if (!Matcher.informative(temporary.item()))
          media.warning =
              "Too little changing visual detail for reliable video comparison. Exact matching"
                  + " remains available.";
      }
    } else {
      Bitmap image =
          ImageDecoder.decodeBitmap(
              ImageDecoder.createSource(context.getContentResolver(), media.uri()),
              (decoder, info, source) -> {
                if (info.isAnimated())
                  throw new IllegalArgumentException(
                      "Animated images currently support exact matching only.");
                decoder.setAllocator(ImageDecoder.ALLOCATOR_SOFTWARE);
                int w = info.getSize().getWidth(), h = info.getSize().getHeight();
                double scale = Math.min(1, 512.0 / Math.max(w, h));
                decoder.setTargetSize(
                    Math.max(1, (int) (w * scale)), Math.max(1, (int) (h * scale)));
              });
      try {
        Matcher.Signature signature = signature(context, image);
        if (signature != null) result.put("photo", Media.json(signature));
        else
          media.warning =
              "Too little visual detail for reliable photo comparison. Exact matching remains"
                  + " available.";
      } finally {
        image.recycle();
      }
    }
    return result.toString();
  }
}
