package com.photofold.mediacleaner;

import android.net.Uri;
import com.photofold.matching.Matcher;
import java.util.*;
import org.json.*;

final class Media {
  String uri,
      name,
      kind,
      mime,
      album,
      identity,
      digest,
      warning = "",
      protection = "",
      descriptor = "";
  long size;
  boolean ready;

  Uri uri() {
    return Uri.parse(uri);
  }

  Matcher.Item item() throws JSONException {
    JSONObject value = new JSONObject(descriptor);
    Matcher.Signature photo = value.has("photo") ? signature(value.getJSONObject("photo")) : null;
    List<Matcher.Frame> frames = new ArrayList<>();
    JSONArray array = value.optJSONArray("frames");
    if (array != null)
      for (int i = 0; i < array.length(); i++) {
        JSONObject frame = array.getJSONObject(i);
        frames.add(new Matcher.Frame(frame.getInt("slot"), signature(frame)));
      }
    return new Matcher.Item(
        uri, name, size, digest, kind, photo, frames, value.optDouble("duration", 0));
  }

  static JSONObject json(Matcher.Signature s) throws JSONException {
    return new JSONObject()
        .put("p", Long.toUnsignedString(s.phash(), 16))
        .put("d", Long.toUnsignedString(s.dhash(), 16))
        .put("aspect", s.aspect())
        .put("red", s.red())
        .put("green", s.green())
        .put("blue", s.blue());
  }

  static Matcher.Signature signature(JSONObject value) throws JSONException {
    return new Matcher.Signature(
        Long.parseUnsignedLong(value.getString("p"), 16),
        Long.parseUnsignedLong(value.getString("d"), 16),
        value.getDouble("aspect"),
        value.getDouble("red"),
        value.getDouble("green"),
        value.getDouble("blue"));
  }
}
