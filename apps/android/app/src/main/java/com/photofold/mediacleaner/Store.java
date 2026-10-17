package com.photofold.mediacleaner;

import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import com.photofold.matching.Matcher;
import java.util.*;
import org.json.*;

final class Store extends SQLiteOpenHelper {
  Store(Context context) {
    super(context, "media-cleaner.sqlite3", null, 1);
    setWriteAheadLoggingEnabled(true);
  }

  @Override
  public void onCreate(SQLiteDatabase db) {
    db.execSQL("CREATE TABLE meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)");
    db.execSQL(
        "CREATE TABLE files (uri TEXT PRIMARY KEY,identity TEXT,name TEXT,kind TEXT,mime TEXT,album"
            + " TEXT,size INTEGER,digest TEXT,descriptor TEXT,warning TEXT,protection TEXT,ready"
            + " INTEGER)");
    db.execSQL(
        "CREATE TABLE groups (id TEXT PRIMARY KEY,classification TEXT,uris TEXT,recommended"
            + " TEXT,updated INTEGER)");
    db.execSQL(
        "CREATE TABLE choices (uri TEXT,identity TEXT,classification TEXT,keep INTEGER,PRIMARY"
            + " KEY(uri,identity,classification))");
    db.execSQL("CREATE TABLE operations (id TEXT PRIMARY KEY,data TEXT,created INTEGER)");
  }

  @Override
  public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
    throw new IllegalStateException("Unsupported database upgrade");
  }

  synchronized String meta(String key, String fallback) {
    try (Cursor c =
        getReadableDatabase().rawQuery("SELECT value FROM meta WHERE key=?", new String[] {key})) {
      return c.moveToFirst() ? c.getString(0) : fallback;
    }
  }

  synchronized void put(String key, String value) {
    ContentValues row = new ContentValues();
    row.put("key", key);
    row.put("value", value);
    getWritableDatabase().insertWithOnConflict("meta", null, row, SQLiteDatabase.CONFLICT_REPLACE);
  }

  synchronized void touch() {
    put("revision", Long.toString(Long.parseLong(meta("revision", "0")) + 1));
  }

  synchronized void recover() {
    if (meta("status", "").equals("running")) {
      put("status", "interrupted");
      put("activity", "Scan interrupted. Choose Resume to use saved file checkpoints.");
      touch();
    }
  }

  synchronized void begin(String album, int total) {
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      db.delete("groups", null, null);
      put("album", album);
      put("total", String.valueOf(total));
      put("processed", "0");
      put("errors", "0");
      put("cached", "0");
      put("status", "running");
      touch();
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  synchronized void save(
      Media media, List<Matcher.Group> changed, int processed, int errors, int cached)
      throws JSONException {
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      ContentValues row = new ContentValues();
      row.put("uri", media.uri);
      row.put("identity", media.identity);
      row.put("name", media.name);
      row.put("kind", media.kind);
      row.put("mime", media.mime);
      row.put("album", media.album);
      row.put("size", media.size);
      row.put("digest", media.digest);
      row.put("descriptor", media.descriptor);
      row.put("warning", media.warning);
      row.put("protection", media.protection);
      row.put("ready", media.ready ? 1 : 0);
      db.insertWithOnConflict("files", null, row, SQLiteDatabase.CONFLICT_REPLACE);
      for (Matcher.Group group : changed)
        if (group.visible()) {
          JSONArray uris = new JSONArray();
          for (Matcher.Item item : group.items) uris.put(item.id());
          ContentValues values = new ContentValues();
          values.put("id", group.id);
          values.put("classification", group.classification);
          values.put("uris", uris.toString());
          values.put("recommended", Matcher.original(group));
          // Keep the first-publication time and row ID when membership grows.
          if (db.update("groups", values, "id=?", new String[] {group.id}) == 0) {
            values.put("updated", System.currentTimeMillis());
            db.insertOrThrow("groups", null, values);
          }
        }
      put("processed", String.valueOf(processed));
      put("errors", String.valueOf(errors));
      put("cached", String.valueOf(cached));
      touch();
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  synchronized void recommend(List<Matcher.Group> groups) {
    for (Matcher.Group group : groups) {
      String original = Matcher.original(group);
      if (original != null) {
        ContentValues values = new ContentValues();
        values.put("recommended", original);
        getWritableDatabase().update("groups", values, "id=?", new String[] {group.id});
      }
    }
  }

  synchronized Media file(String uri) {
    try (Cursor c =
        getReadableDatabase().query("files", null, "uri=?", new String[] {uri}, null, null, null)) {
      if (!c.moveToFirst()) return null;
      Media m = new Media();
      m.uri = uri;
      m.identity = text(c, "identity");
      m.name = text(c, "name");
      m.kind = text(c, "kind");
      m.mime = text(c, "mime");
      m.album = text(c, "album");
      m.size = c.getLong(c.getColumnIndexOrThrow("size"));
      m.digest = text(c, "digest");
      m.descriptor = text(c, "descriptor");
      m.warning = text(c, "warning");
      m.protection = text(c, "protection");
      m.ready = c.getInt(c.getColumnIndexOrThrow("ready")) == 1;
      return m;
    }
  }

  static String text(Cursor c, String column) {
    return c.getString(c.getColumnIndexOrThrow(column));
  }

  record Group(String id, String classification, List<Media> files, String recommended) {}

  synchronized Group group(String id) {
    try (Cursor c =
        getReadableDatabase().rawQuery("SELECT * FROM groups WHERE id=?", new String[] {id})) {
      return c.moveToFirst() ? readGroup(c) : null;
    }
  }

  private Group readGroup(Cursor c) {
    List<Media> files = new ArrayList<>();
    try {
      JSONArray uris = new JSONArray(text(c, "uris"));
      for (int i = 0; i < uris.length(); i++) {
        Media m = file(uris.getString(i));
        if (m != null && m.ready) files.add(m);
      }
    } catch (JSONException e) {
      throw new IllegalStateException(e);
    }
    return new Group(text(c, "id"), text(c, "classification"), files, text(c, "recommended"));
  }

  synchronized List<Group> groups(int limit) {
    return groups(limit, "", 0);
  }

  synchronized List<Group> groups(int limit, String classification, int sort) {
    List<Group> result = new ArrayList<>();
    try (Cursor c =
        getReadableDatabase()
            .rawQuery(
                "SELECT * FROM groups WHERE (?='' OR classification=?) ORDER BY "
                    + (sort == 1
                        ? "CASE WHEN classification='EXACT_DUPLICATE' THEN 0 ELSE 1 END,"
                        : "")
                    + "updated ASC,rowid ASC LIMIT ?",
                new String[] {
                  classification,
                  classification,
                  String.valueOf(sort < 2 ? limit : Integer.MAX_VALUE)
                })) {
      while (c.moveToNext()) {
        Group group = readGroup(c);
        if (group.files.size() > 1) result.add(group);
      }
    }
    if (sort == 2)
      result.sort(
          java.util.Comparator.comparingLong(
                  (Group group) -> {
                    long total = group.files.stream().mapToLong(file -> file.size).sum();
                    long retained =
                        group.files.stream().mapToLong(file -> file.size).max().orElse(0);
                    return total - retained;
                  })
              .reversed());
    if (sort == 3)
      result.sort(
          java.util.Comparator.comparingInt((Group group) -> group.files.size()).reversed());
    return new ArrayList<>(result.subList(0, Math.min(limit, result.size())));
  }

  synchronized void approve(String groupId) {
    Group group = group(groupId);
    if (group == null) throw new IllegalArgumentException("Group changed. Reopen review.");
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      for (Media file : group.files) select(groupId, file.uri, !keep(group, file));
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  synchronized int groupCount() {
    return groupCount("");
  }

  synchronized int groupCount(String classification) {
    try (Cursor c =
        getReadableDatabase()
            .rawQuery(
                "SELECT COUNT(*) FROM groups WHERE (?='' OR classification=?)",
                new String[] {classification, classification})) {
      c.moveToFirst();
      return c.getInt(0);
    }
  }

  synchronized boolean keep(Group group, Media file) {
    try (Cursor c =
        getReadableDatabase()
            .rawQuery(
                "SELECT keep FROM choices WHERE uri=? AND identity=? AND classification=?",
                new String[] {file.uri, file.identity, group.classification})) {
      if (c.moveToFirst()) return c.getInt(0) != 0;
    }
    return group.recommended == null
        || group.recommended.equals(file.uri)
        || !file.protection.isEmpty();
  }

  synchronized void select(String groupId, String uri, boolean selected) {
    select(groupId, uri, selected, false);
  }

  private void select(String groupId, String uri, boolean selected, boolean all) {
    Group group = group(groupId);
    if (group == null) throw new IllegalArgumentException("Group changed. Reopen comparison.");
    Media file =
        group.files.stream().filter(item -> item.uri.equals(uri)).findFirst().orElseThrow();
    if (selected && !file.protection.isEmpty()) throw new IllegalArgumentException(file.protection);
    if (selected
        && !all
        && keep(group, file)
        && group.classification.equals("EXACT_DUPLICATE")
        && group.files.stream().noneMatch(item -> !item.uri.equals(uri) && keep(group, item)))
      throw new IllegalArgumentException(
          "Keep at least one file. Keep another copy first to change the keeper.");
    ContentValues values = new ContentValues();
    values.put("uri", uri);
    values.put("identity", file.identity);
    values.put("classification", group.classification);
    values.put("keep", selected ? 0 : 1);
    if (!selected) put("keepNone:" + groupId, "");
    getWritableDatabase()
        .insertWithOnConflict("choices", null, values, SQLiteDatabase.CONFLICT_REPLACE);
    touch();
  }

  synchronized boolean reviewed(Group group) {
    for (Media file : group.files()) {
      try (Cursor c =
          getReadableDatabase()
              .rawQuery(
                  "SELECT 1 FROM choices WHERE uri=? AND identity=? AND classification=?",
                  new String[] {file.uri, file.identity, group.classification()})) {
        if (c.moveToFirst()) return true;
      }
    }
    return false;
  }

  private String keepNoneSignature(Group group) {
    return group.files.stream()
        .map(file -> file.uri + ":" + file.identity)
        .sorted()
        .collect(java.util.stream.Collectors.joining("\n"));
  }

  synchronized boolean explicitKeepNone(Group group) {
    return !group.files.isEmpty()
        && meta("keepNone:" + group.id, "").equals(keepNoneSignature(group))
        && group.files.stream().noneMatch(file -> keep(group, file));
  }

  synchronized void selectAll(String groupId) {
    Group group = group(groupId);
    if (group == null) throw new IllegalArgumentException("Group changed. Reopen review.");
    if (group.files.stream().anyMatch(file -> !file.protection.isEmpty()))
      throw new IllegalArgumentException(
          "This group contains protected media. Protected files must be kept.");
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      for (Media file : group.files) select(groupId, file.uri, true, true);
      put("keepNone:" + groupId, keepNoneSignature(group));
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  synchronized void operation(JSONObject data) throws JSONException {
    ContentValues values = new ContentValues();
    values.put("id", data.getString("id"));
    values.put("data", data.toString());
    values.put("created", data.getLong("created"));
    getWritableDatabase()
        .insertWithOnConflict("operations", null, values, SQLiteDatabase.CONFLICT_REPLACE);
    touch();
  }

  synchronized void removeFromResults(JSONArray items) throws JSONException {
    SQLiteDatabase db = getWritableDatabase();
    db.beginTransaction();
    try {
      for (int i = 0; i < items.length(); i++) {
        ContentValues value = new ContentValues();
        value.put("ready", 0);
        db.update("files", value, "uri=?", new String[] {items.getJSONObject(i).getString("uri")});
      }
      try (Cursor c = db.rawQuery("SELECT id FROM groups", null)) {
        List<String> resolved = new ArrayList<>();
        while (c.moveToNext()) {
          Group group = group(c.getString(0));
          if (group == null || group.files.size() < 2) resolved.add(c.getString(0));
        }
        for (String id : resolved) db.delete("groups", "id=?", new String[] {id});
      }
      touch();
      db.setTransactionSuccessful();
    } finally {
      db.endTransaction();
    }
  }

  synchronized List<JSONObject> operations() {
    List<JSONObject> values = new ArrayList<>();
    try (Cursor c =
        getReadableDatabase()
            .rawQuery("SELECT data FROM operations ORDER BY created DESC LIMIT 10", null)) {
      while (c.moveToNext())
        try {
          values.add(new JSONObject(c.getString(0)));
        } catch (JSONException ignored) {
        }
    }
    return values;
  }
}
