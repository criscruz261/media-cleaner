package com.photofold.mediacleaner;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.net.Uri;
import android.os.*;
import android.provider.MediaStore;
import android.util.*;
import android.view.*;
import android.widget.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

public final class MainActivity extends Activity {
  private Store store;
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final ExecutorService io = Executors.newSingleThreadExecutor(),
      thumbnails = Executors.newFixedThreadPool(2);
  private final LruCache<String, Bitmap> images =
      new LruCache<>(16 * 1024) {
        @Override
        protected int sizeOf(String key, Bitmap bitmap) {
          return bitmap.getByteCount() / 1024;
        }
      };
  private LinearLayout groups, history;
  private TextView progress, activity, access;
  private ProgressBar bar;
  private Spinner albums;
  private Button start, pause, resume;
  private String stamp = "";
  private int limit = 5;
  private boolean cleanupBusy = false;
  private Dialog comparison;
  private static final int PERMISSIONS = 10, TRASH = 20, RESTORE = 21;
  private final Runnable tick =
      new Runnable() {
        @Override
        public void run() {
          refresh();
          handler.postDelayed(this, 1200);
        }
      };

  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    store = ((CleanerApp) getApplication()).store;
    ScrollView scroll = new ScrollView(this);
    LinearLayout body = column();
    scroll.addView(body);
    setContentView(scroll);
    body.setBackgroundColor(0xfff7f8f5);
    body.setOnApplyWindowInsetsListener(
        (view, insets) -> {
          android.graphics.Insets edges = insets.getInsets(WindowInsets.Type.systemBars());
          body.setPadding(
              dp(16) + edges.left, dp(18) + edges.top, dp(16) + edges.right, dp(24) + edges.bottom);
          return insets;
        });
    heading(body, "Media Cleaner", 28);
    label(
        body,
        "Find exact copies and similar photos/videos on this phone. Everything stays on-device.");
    access = label(body, "");
    button(body, "Allow / change photo and video access", this::requestAccess);
    albums = new Spinner(this);
    albums.setAdapter(
        new ArrayAdapter<>(
            this, android.R.layout.simple_spinner_dropdown_item, List.of("All accessible media")));
    body.addView(albums);
    LinearLayout actions = row();
    body.addView(actions);
    start = button(actions, "Scan", () -> start(false));
    pause = button(actions, "Pause", () -> ScanService.paused.set(true));
    resume = button(actions, "Resume", () -> start(true));
    progress = label(body, "");
    bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
    body.addView(bar);
    activity = label(body, "");
    label(
        body,
        "Completed files and selections are saved automatically in app storage. Resume revalidates"
            + " access and reuses unchanged files. App data survives closing and rotation, but not"
            + " uninstall or Clear storage.");
    heading(body, "Matches found so far", 22);
    label(
        body,
        "Select unwanted files for deletion. Keep at least one file per group. Android asks for"
            + " confirmation before moving anything to Trash.");
    groups = column();
    body.addView(groups);
    button(
        body,
        "Show more groups",
        () -> {
          limit += 5;
          stamp = "";
          refresh();
        });
    heading(body, "Cleanup and recovery", 22);
    label(
        body,
        "Trash retention is managed by Android. Restore through this history or your gallery’s"
            + " Trash before the device removes expired items.");
    history = column();
    body.addView(history);
    if (getIntent().getBooleanExtra("fixtureScan", false)
        && (getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
        && hasAccess()) start(false);
  }

  @Override
  protected void onResume() {
    super.onResume();
    handler.post(tick);
    loadAlbums();
  }

  @Override
  protected void onPause() {
    handler.removeCallbacks(tick);
    super.onPause();
  }

  @Override
  protected void onDestroy() {
    handler.removeCallbacks(tick);
    if (comparison != null) comparison.dismiss();
    io.shutdown();
    thumbnails.shutdown();
    super.onDestroy();
  }

  private int dp(int value) {
    return (int) (value * getResources().getDisplayMetrics().density);
  }

  private LinearLayout column() {
    LinearLayout layout = new LinearLayout(this);
    layout.setOrientation(LinearLayout.VERTICAL);
    layout.setPadding(dp(8), dp(8), dp(8), dp(8));
    return layout;
  }

  private LinearLayout row() {
    LinearLayout layout = new LinearLayout(this);
    layout.setOrientation(LinearLayout.HORIZONTAL);
    return layout;
  }

  private TextView label(LinearLayout parent, String text) {
    TextView view = new TextView(this);
    view.setText(text);
    view.setTextSize(14);
    view.setTextColor(0xff233c32);
    view.setPadding(0, dp(5), 0, dp(5));
    parent.addView(view);
    return view;
  }

  private void heading(LinearLayout parent, String text, int size) {
    TextView view = label(parent, text);
    view.setTextSize(size);
    view.setTypeface(null, Typeface.BOLD);
  }

  private Button button(LinearLayout parent, String text, Runnable action) {
    Button view = new Button(this);
    view.setText(text);
    view.setAllCaps(false);
    view.setOnClickListener(ignored -> action.run());
    parent.addView(view);
    return view;
  }

  private void message(String text) {
    if (!isDestroyed())
      new AlertDialog.Builder(this)
          .setTitle("Media Cleaner")
          .setMessage(text)
          .setPositiveButton("OK", null)
          .show();
  }

  private boolean granted(String permission) {
    return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
  }

  private boolean hasAccess() {
    return Build.VERSION.SDK_INT < 33
        ? granted(Manifest.permission.READ_EXTERNAL_STORAGE)
        : granted(Manifest.permission.READ_MEDIA_IMAGES)
            || granted(Manifest.permission.READ_MEDIA_VIDEO)
            || (Build.VERSION.SDK_INT >= 34
                && granted(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED));
  }

  private void requestAccess() {
    List<String> permissions = new ArrayList<>();
    if (Build.VERSION.SDK_INT < 33) permissions.add(Manifest.permission.READ_EXTERNAL_STORAGE);
    else {
      permissions.add(Manifest.permission.READ_MEDIA_IMAGES);
      permissions.add(Manifest.permission.READ_MEDIA_VIDEO);
      if (Build.VERSION.SDK_INT >= 34)
        permissions.add(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED);
      permissions.add(Manifest.permission.POST_NOTIFICATIONS);
    }
    requestPermissions(permissions.toArray(new String[0]), PERMISSIONS);
  }

  @Override
  public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
    super.onRequestPermissionsResult(request, permissions, results);
    loadAlbums();
    stamp = "";
    refresh();
  }

  private void loadAlbums() {
    if (!hasAccess()) return;
    io.submit(
        () -> {
          try {
            List<Media> media = MediaRepository.discover(this, "", () -> {});
            Set<String> distinct = new TreeSet<>();
            for (Media item : media) if (!item.album.isEmpty()) distinct.add(item.album);
            List<String> values = new ArrayList<>();
            values.add("All accessible media");
            values.addAll(distinct);
            runOnUiThread(
                () -> {
                  if (isDestroyed()) return;
                  String previous = String.valueOf(albums.getSelectedItem());
                  albums.setAdapter(
                      new ArrayAdapter<>(
                          this, android.R.layout.simple_spinner_dropdown_item, values));
                  int index = values.indexOf(previous);
                  if (index < 0) index = values.indexOf(store.meta("album", ""));
                  albums.setSelection(Math.max(0, index));
                });
          } catch (Exception failure) {
            runOnUiThread(() -> message("Unable to list albums. Check media access."));
          }
        });
  }

  private void start(boolean restore) {
    if (!store.meta("pendingOperation", "").isEmpty()) {
      message(
          "Resolve the pending cleanup request in Cleanup and recovery before starting a scan.");
      return;
    }
    if (!hasAccess()) {
      requestAccess();
      return;
    }
    if (cleanupBusy) return;
    String album =
        restore
            ? store.meta("album", "")
            : (albums.getSelectedItemPosition() == 0
                ? ""
                : String.valueOf(albums.getSelectedItem()));
    startForegroundService(new Intent(this, ScanService.class).putExtra("album", album));
  }

  private void refresh() {
    if (progress == null || isDestroyed()) return;
    boolean active = ScanService.running.get();
    String status = store.meta("status", "ready");
    access.setText(
        !hasAccess()
            ? "No media access. Allow access to scan."
            : Build.VERSION.SDK_INT >= 34
                    && !granted(Manifest.permission.READ_MEDIA_IMAGES)
                    && !granted(Manifest.permission.READ_MEDIA_VIDEO)
                ? "Selected media access: only items you allowed will be scanned."
                : "Scanning is limited to the media access granted by Android.");
    start.setEnabled(!active && !cleanupBusy);
    resume.setEnabled(!active && !cleanupBusy && !store.meta("status", "").isEmpty());
    pause.setEnabled(active && !ScanService.paused.get());
    albums.setEnabled(!active && !cleanupBusy);
    int total = Integer.parseInt(store.meta("total", "0")),
        done = Integer.parseInt(store.meta("processed", "0"));
    progress.setText(
        status
            + " · "
            + done
            + " / "
            + total
            + " saved · "
            + store.meta("cached", "0")
            + " cached · "
            + store.meta("errors", "0")
            + " errors");
    bar.setMax(Math.max(1, total));
    bar.setProgress(done);
    activity.setText(store.meta("activity", "Choose media access, then Scan."));
    List<Store.Group> found = store.groups(limit);
    StringBuilder identity = new StringBuilder();
    for (Store.Group group : found) {
      identity.append(group.id()).append(group.recommended());
      for (Media file : group.files())
        identity
            .append(file.uri)
            .append(file.identity)
            .append(store.keep(group, file))
            .append(file.warning);
    }
    identity.append(store.operations().toString()).append(cleanupBusy).append(limit);
    if (stamp.equals(identity.toString())) return;
    stamp = identity.toString();
    groups.removeAllViews();
    if (found.isEmpty())
      label(
          groups,
          active
              ? "Matches appear as soon as files are compared."
              : "No matching groups yet. Run a scan to compare accessible media.");
    for (Store.Group group : found) renderGroup(group);
    label(groups, "Showing " + found.size() + " of " + store.groupCount() + " groups");
    renderHistory();
  }

  private CheckBox selection(LinearLayout parent, Store.Group group, Media file) {
    CheckBox check = new CheckBox(this);
    check.setText("Select " + file.name + " for deletion");
    check.setChecked(!store.keep(group, file));
    check.setEnabled(file.protection.isEmpty() && !cleanupBusy);
    check.setOnClickListener(
        view -> {
          boolean selected = check.isChecked();
          try {
            store.select(group.id(), file.uri, selected);
          } catch (Exception failure) {
            check.setChecked(!selected);
            message(failure.getMessage());
          }
          stamp = "";
          refresh();
        });
    parent.addView(check);
    return check;
  }

  private void thumbnail(LinearLayout parent, Media file, Runnable open) {
    ImageView view = new ImageView(this);
    view.setContentDescription("Thumbnail of " + file.name);
    view.setScaleType(ImageView.ScaleType.FIT_CENTER);
    view.setBackgroundColor(0xffedf2e9);
    parent.addView(view, new LinearLayout.LayoutParams(-1, dp(180)));
    view.setOnClickListener(ignored -> open.run());
    String key = file.identity;
    view.setTag(key);
    Bitmap cached = images.get(key);
    if (cached != null) {
      view.setImageBitmap(cached);
      return;
    }
    thumbnails.submit(
        () -> {
          try {
            Bitmap bitmap =
                getContentResolver().loadThumbnail(file.uri(), new Size(320, 220), null);
            images.put(key, bitmap);
            runOnUiThread(
                () -> {
                  if (!isDestroyed() && key.equals(view.getTag())) view.setImageBitmap(bitmap);
                });
          } catch (Exception failure) {
            runOnUiThread(() -> view.setContentDescription("Thumbnail unavailable: " + file.name));
          }
        });
  }

  private void renderGroup(Store.Group group) {
    LinearLayout card = column();
    card.setBackgroundColor(0xffffffff);
    groups.addView(card);
    heading(
        card,
        (group.classification().equals("EXACT_DUPLICATE") ? "Exact copies" : "Similar media")
            + " · "
            + group.files().size()
            + " files",
        18);
    label(
        card,
        group.classification().equals("EXACT_DUPLICATE")
            ? "Same size and full SHA-256. Original-name suggestions are advisory."
            : "Approximate pHash/dHash appearance, complete-link grouping. Videos compare nine"
                + " time-spaced samples. Audio and unsampled moments may differ; all files start"
                + " kept.");
    if (group.files().stream().filter(m -> m.kind.equals("video")).count() >= 2)
      button(card, "Compare similar videos", () -> compare(group.id()));
    LinearLayout members = column();
    card.addView(members);
    renderMembers(members, group, 4);
    if (group.files().size() > 4)
      button(
          card,
          "Show all " + group.files().size() + " files",
          () -> {
            members.removeAllViews();
            renderMembers(members, group, Math.min(group.files().size(), 50));
            if (group.files().size() > 50)
              label(
                  members,
                  "Showing first 50 files. Video comparison pages through the full video group.");
          });
    Button selectAll =
        button(
            card,
            "Select all for deletion (keep none)",
            () -> {
              try {
                store.selectAll(group.id());
                stamp = "";
                refresh();
              } catch (Exception failure) {
                message(failure.getMessage());
              }
            });
    selectAll.setEnabled(!cleanupBusy);
    long selected = group.files().stream().filter(file -> !store.keep(group, file)).count();
    Button delete = button(card, "Delete selected (" + selected + ")", () -> preview(group.id()));
    delete.setContentDescription(
        (group.files().stream().allMatch(file -> file.kind.equals("video"))
                ? "Delete selected videos ("
                : "Delete selected photos (")
            + selected
            + ")");
    delete.setEnabled(selected > 0 && !cleanupBusy);
  }

  private void renderMembers(LinearLayout parent, Store.Group group, int count) {
    for (Media file : group.files().subList(0, Math.min(count, group.files().size()))) {
      selection(parent, group, file);
      thumbnail(parent, file, () -> open(file));
      label(
          parent, file.name + " · " + String.format(Locale.ROOT, "%.1f MB", file.size / 1048576.0));
      if (!file.warning.isEmpty()) label(parent, file.warning);
      if (!file.protection.isEmpty()) label(parent, file.protection);
    }
  }

  private void open(Media file) {
    if (file.kind.equals("video")) {
      try {
        startActivity(
            new Intent(Intent.ACTION_VIEW)
                .setDataAndType(file.uri(), file.mime)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
      } catch (ActivityNotFoundException noPlayer) {
        message("No video player is available. Use Compare similar videos.");
      }
    } else {
      Dialog dialog = new Dialog(this);
      ScrollView scroll = new ScrollView(this);
      LinearLayout body = column();
      scroll.addView(body);
      ImageView image = new ImageView(this);
      image.setAdjustViewBounds(true);
      body.addView(image);
      button(body, "Close preview", dialog::dismiss);
      dialog.setContentView(scroll);
      dialog.show();
      thumbnails.submit(
          () -> {
            try {
              Bitmap bitmap =
                  getContentResolver().loadThumbnail(file.uri(), new Size(1200, 1200), null);
              runOnUiThread(
                  () -> {
                    if (dialog.isShowing()) image.setImageBitmap(bitmap);
                  });
            } catch (Exception failure) {
              runOnUiThread(() -> message("Preview unavailable for this media."));
            }
          });
    }
  }

  private void compare(String groupId) {
    Store.Group group = store.group(groupId);
    if (group == null) return;
    List<Media> videos =
        group.files().stream()
            .filter(file -> file.kind.equals("video"))
            .collect(java.util.stream.Collectors.toList());
    Dialog dialog = new Dialog(this);
    comparison = dialog;
    ScrollView scroll = new ScrollView(this);
    LinearLayout content = column();
    scroll.addView(content);
    heading(content, "Compare similar videos", 22);
    label(
        content,
        "Starts muted. Unmute individual videos to compare audio. Up to four players per page;"
            + " buffering can affect timing.");
    LinearLayout controls = row();
    content.addView(controls);
    List<VideoView> players = new ArrayList<>();
    Set<VideoView> prepared = new HashSet<>();
    Button play =
        button(
            controls,
            "Play all",
            () -> {
              for (VideoView video : players) {
                video.seekTo(0);
                video.start();
              }
            });
    button(
        controls,
        "Pause all",
        () -> {
          for (VideoView video : players) video.pause();
        });
    button(
        content,
        "Reset all",
        () -> {
          for (VideoView video : players) {
            video.pause();
            video.seekTo(0);
          }
        });
    LinearLayout cards = column();
    content.addView(cards);
    int[] page = {0};
    Runnable render =
        new Runnable() {
          @Override
          public void run() {
            for (VideoView player : players) player.stopPlayback();
            players.clear();
            prepared.clear();
            cards.removeAllViews();
            play.setEnabled(false);
            int end = Math.min(page[0] + 4, videos.size());
            label(
                cards, "Showing " + (page[0] + 1) + "–" + end + " of " + videos.size() + " videos");
            Store.Group latest = store.group(groupId);
            if (latest == null) {
              dialog.dismiss();
              return;
            }
            for (Media file : videos.subList(page[0], end)) {
              selection(cards, latest, file);
              label(cards, file.name);
              if (!file.protection.isEmpty()) label(cards, file.protection);
              VideoView video = new VideoView(MainActivity.this);
              players.add(video);
              cards.addView(video, new LinearLayout.LayoutParams(-1, dp(210)));
              MediaController controller = new MediaController(MainActivity.this);
              controller.setAnchorView(video);
              video.setMediaController(controller);
              android.media.MediaPlayer[] audio = {null};
              CheckBox sound = new CheckBox(MainActivity.this);
              sound.setText("Audio: " + file.name);
              cards.addView(sound);
              sound.setOnCheckedChangeListener(
                  (button, enabled) -> {
                    if (audio[0] != null) audio[0].setVolume(enabled ? 1 : 0, enabled ? 1 : 0);
                  });
              video.setOnPreparedListener(
                  player -> {
                    audio[0] = player;
                    player.setVolume(0, 0);
                    video.seekTo(1);
                    prepared.add(video);
                    play.setEnabled(prepared.size() == players.size());
                  });
              video.setOnErrorListener(
                  (player, what, extra) -> {
                    label(
                        cards,
                        "Playback unavailable for " + file.name + ". Try the gallery player.");
                    players.remove(video);
                    play.setEnabled(!players.isEmpty() && prepared.containsAll(players));
                    return true;
                  });
              video.setVideoURI(file.uri());
            }
            if (page[0] > 0)
              button(
                  cards,
                  "Previous videos",
                  () -> {
                    page[0] -= 4;
                    run();
                  });
            if (end < videos.size())
              button(
                  cards,
                  "Next videos",
                  () -> {
                    page[0] += 4;
                    run();
                  });
          }
        };
    render.run();
    button(content, "Close comparison", dialog::dismiss);
    dialog.setContentView(scroll);
    dialog.setOnDismissListener(
        ignored -> {
          for (VideoView player : players) player.stopPlayback();
          comparison = null;
          stamp = "";
          refresh();
        });
    dialog.show();
    dialog.getWindow().setLayout(-1, -1);
  }

  private void preview(String groupId) {
    if (cleanupBusy) return;
    if (!store.meta("pendingOperation", "").isEmpty()) {
      message(
          "A previous cleanup request is unresolved. Check its result or dismiss it in Cleanup and"
              + " recovery.");
      return;
    }
    boolean wasRunning = ScanService.running.get();
    cleanupBusy = true;
    ScanService.paused.set(true);
    stamp = "";
    refresh();
    activity.setText("Pausing scan briefly to prepare cleanup…");
    io.submit(
        () -> {
          try {
            long deadline = SystemClock.elapsedRealtime() + 30_000;
            while (ScanService.running.get() && SystemClock.elapsedRealtime() < deadline)
              Thread.sleep(50);
            if (ScanService.running.get())
              throw new IllegalStateException(
                  "The scanner is still stopping. Retry once it is paused.");
            Store.Group group = store.group(groupId);
            if (group == null)
              throw new IllegalArgumentException(
                  "Group changed. Resume or rescan before reviewing.");
            List<Media> selected =
                group.files().stream()
                    .filter(file -> !store.keep(group, file))
                    .collect(java.util.stream.Collectors.toList());
            Media keeper =
                group.files().stream()
                    .filter(file -> store.keep(group, file))
                    .findFirst()
                    .orElse(null);
            if (selected.isEmpty() || selected.size() > 100)
              throw new IllegalArgumentException("Choose 1–100 files per cleanup.");
            List<Media> current = MediaRepository.discover(this, store.meta("album", ""), () -> {});
            JSONArray items = new JSONArray();
            for (Media file : selected) {
              if (!file.protection.isEmpty()
                  || current.stream()
                      .anyMatch(m -> m.uri.equals(file.uri) && !m.protection.isEmpty()))
                throw new IllegalArgumentException(
                    "Protected media cannot be removed: " + file.name);
              if (!MediaRepository.unchanged(this, file)
                  || (keeper != null && !MediaRepository.unchanged(this, keeper)))
                throw new IllegalArgumentException(
                    "Selected or retained media changed. Rescan first.");
              items.put(
                  new JSONObject()
                      .put("uri", file.uri)
                      .put("name", file.name)
                      .put("identity", file.identity)
                      .put("digest", file.digest)
                      .put("keeper", keeper == null ? "" : keeper.uri)
                      .put("keeperIdentity", keeper == null ? "" : keeper.identity)
                      .put("keeperDigest", keeper == null ? "" : keeper.digest));
            }
            JSONObject plan =
                new JSONObject()
                    .put("id", UUID.randomUUID().toString())
                    .put("created", System.currentTimeMillis())
                    .put("kind", "trash")
                    .put("status", "preview")
                    .put("resume", wasRunning)
                    .put("group", group.id())
                    .put("classification", group.classification())
                    .put("items", items);
            store.operation(plan);
            store.put("pendingOperation", plan.getString("id"));
            runOnUiThread(
                () -> {
                  if (isDestroyed()) return;
                  showPreview(plan);
                });
          } catch (Exception failure) {
            runOnUiThread(
                () -> {
                  cleanupBusy = false;
                  stamp = "";
                  refresh();
                  message(failure.getMessage());
                  if (wasRunning) start(true);
                });
          }
        });
  }

  private void showPreview(JSONObject plan) {
    LinearLayout body = column();
    JSONArray items = plan.optJSONArray("items");
    label(
        body,
        items.length() + " files will move to Android Trash. No permanent deletion is performed.");
    if ("SIMILAR_CONTENT".equals(plan.optString("classification")))
      label(
          body,
          "These files are visually similar; they may contain different moments or audio. Compare"
              + " full playback before confirming.");
    for (int i = 0; i < items.length(); i++) label(body, items.optJSONObject(i).optString("name"));
    String keeperUri = items.optJSONObject(0).optString("keeper");
    Media retained = keeperUri.isEmpty() ? null : store.file(keeperUri);
    label(
        body,
        retained == null
            ? "Keep none: every selected file will move to Trash. No copy will remain in this"
                  + " group."
            : "Retained: "
                + retained.name
                + ". Selected and retained files will be freshly hashed before Android"
                + " confirmation.");
    CheckBox confirmed = new CheckBox(this);
    confirmed.setText("I reviewed these files and want to move them to Trash");
    body.addView(confirmed);
    ScrollView review = new ScrollView(this);
    review.addView(body);
    AlertDialog dialog =
        new AlertDialog.Builder(this)
            .setTitle("Confirm group cleanup")
            .setView(review)
            .setPositiveButton(
                "Continue to Android confirmation", (d, which) -> validateAndTrash(plan))
            .setNegativeButton("Cancel", (d, which) -> cancel(plan))
            .create();
    dialog.setOnCancelListener(ignored -> cancel(plan));
    dialog.setOnShowListener(
        ignored -> {
          dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
          confirmed.setOnCheckedChangeListener(
              (view, value) -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(value));
        });
    dialog.show();
  }

  private void validateAndTrash(JSONObject plan) {
    activity.setText("Verifying media contents before cleanup…");
    io.submit(
        () -> {
          try {
            plan.put("status", "validating");
            store.operation(plan);
            if (System.currentTimeMillis() - plan.getLong("created") > 10 * 60 * 1000)
              throw new IllegalArgumentException("Cleanup preview expired. Create a new preview.");
            MediaRepository.Check notCancelled =
                () -> {
                  if (!plan.optString("id").equals(store.meta("pendingOperation", "")))
                    throw new CancellationException("Cleanup request was cancelled");
                };
            notCancelled.run();
            List<Media> current =
                MediaRepository.discover(this, store.meta("album", ""), notCancelled);
            JSONArray items = plan.getJSONArray("items");
            List<Uri> uris = new ArrayList<>();
            Set<String> verified = new HashSet<>();
            for (int i = 0; i < items.length(); i++) {
              JSONObject item = items.getJSONObject(i);
              Media selected = store.file(item.getString("uri")),
                  keeper = store.file(item.getString("keeper"));
              if (selected == null
                  || (!item.getString("keeper").isEmpty() && keeper == null)
                  || !selected.identity.equals(item.getString("identity"))
                  || (keeper != null && !keeper.identity.equals(item.getString("keeperIdentity"))))
                throw new IllegalArgumentException(
                    "Media identity changed. Rescan before cleanup.");
              notCancelled.run();
              if (!selected.protection.isEmpty()
                  || current.stream()
                      .anyMatch(
                          file -> file.uri.equals(selected.uri) && !file.protection.isEmpty()))
                throw new IllegalArgumentException("A selected file is protected. Rescan first.");
              Store.Group group = store.group(plan.getString("group"));
              if (group == null
                  || group.files().stream().noneMatch(file -> file.uri.equals(selected.uri))
                  || store.keep(group, selected)
                  || (keeper != null
                      ? !store.keep(group, keeper)
                      : group.files().stream().anyMatch(file -> store.keep(group, file))))
                throw new IllegalArgumentException("Keep choices changed. Create a new preview.");
              for (Media file : keeper == null ? List.of(selected) : List.of(selected, keeper))
                if (verified.add(file.uri)) {
                  String digest = MediaRepository.hash(this, file, notCancelled, ignored -> {});
                  String expected =
                      file == selected ? item.getString("digest") : item.getString("keeperDigest");
                  if (!digest.equals(expected))
                    throw new IllegalArgumentException("Media contents changed. Rescan first.");
                }
              uris.add(selected.uri());
            }
            notCancelled.run();
            PendingIntent request = MediaStore.createTrashRequest(getContentResolver(), uris, true);
            plan.put("status", "awaiting_android");
            store.operation(plan);
            runOnUiThread(() -> launchSystem(request, TRASH, plan));
          } catch (Exception failure) {
            runOnUiThread(
                () -> {
                  cancel(plan);
                  message("Cleanup blocked: " + failure.getMessage());
                });
          }
        });
  }

  private void launchSystem(PendingIntent request, int code, JSONObject plan) {
    if (isDestroyed() || !plan.optString("id").equals(store.meta("pendingOperation", ""))) return;
    try {
      startIntentSenderForResult(request.getIntentSender(), code, null, 0, 0, 0);
    } catch (IntentSender.SendIntentException failure) {
      cancel(plan);
      message("Android could not open the confirmation dialog.");
    }
  }

  private JSONObject pending() {
    String id = store.meta("pendingOperation", "");
    return store.operations().stream()
        .filter(item -> id.equals(item.optString("id")))
        .findFirst()
        .orElse(null);
  }

  private void cancel(JSONObject plan) {
    try {
      plan.put("status", "cancelled");
      store.operation(plan);
    } catch (JSONException ignored) {
    }
    store.put("pendingOperation", "");
    cleanupBusy = false;
    stamp = "";
    refresh();
    if (plan.optBoolean("resume")) start(true);
  }

  @Override
  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (request != TRASH && request != RESTORE) return;
    JSONObject plan = pending();
    if (plan == null) return;
    if (result != RESULT_OK) {
      cancel(plan);
      return;
    }
    finishOperation(plan);
  }

  private void finishOperation(JSONObject plan) {
    try {
      boolean restore = plan.optString("kind").equals("restore");
      plan.put("status", restore ? "restored" : "trashed");
      store.operation(plan);
      if (restore) {
        String original = plan.optString("original");
        for (JSONObject previous : store.operations())
          if (previous.optString("id").equals(original)) {
            previous.put("status", "restored");
            store.operation(previous);
          }
      }
      store.removeFromResults(plan.getJSONArray("items"));
      store.put("pendingOperation", "");
    } catch (JSONException failure) {
      message("Android confirmed the operation. Rescan to refresh results.");
    }
    cleanupBusy = false;
    stamp = "";
    refresh();
    if (plan.optBoolean("resume")) start(true);
  }

  private void restore(JSONObject operation) {
    new AlertDialog.Builder(this)
        .setTitle("Restore photos/videos from Android Trash?")
        .setMessage(
            "Android will ask you to confirm restoring these items. Files already expired or"
                + " removed by the device may be unavailable.")
        .setPositiveButton(
            "Continue",
            (dialog, which) -> {
              try {
                if (!store.meta("pendingOperation", "").isEmpty()) {
                  message("Resolve the previous cleanup request first.");
                  return;
                }
                List<Uri> uris = new ArrayList<>();
                JSONArray items = operation.getJSONArray("items");
                for (int i = 0; i < items.length(); i++)
                  uris.add(Uri.parse(items.getJSONObject(i).getString("uri")));
                JSONObject plan =
                    new JSONObject(operation.toString())
                        .put("id", UUID.randomUUID().toString())
                        .put("original", operation.getString("id"))
                        .put("created", System.currentTimeMillis())
                        .put("kind", "restore")
                        .put("status", "awaiting_android")
                        .put("resume", false);
                PendingIntent request =
                    MediaStore.createTrashRequest(getContentResolver(), uris, false);
                store.operation(plan);
                store.put("pendingOperation", plan.getString("id"));
                launchSystem(request, RESTORE, plan);
              } catch (Exception failure) {
                message(
                    "Restore unavailable: "
                        + failure.getClass().getSimpleName()
                        + ". Check the gallery’s Trash.");
              }
            })
        .setNegativeButton("Cancel", null)
        .show();
  }

  private void renderHistory() {
    history.removeAllViews();
    for (JSONObject operation : store.operations()) {
      LinearLayout card = column();
      history.addView(card);
      String status = operation.optString("status");
      label(
          card,
          status
              + " · "
              + operation.optJSONArray("items").length()
              + " files · "
              + new java.text.SimpleDateFormat("MMM d HH:mm", Locale.getDefault())
                  .format(new Date(operation.optLong("created"))));
      if (status.equals("trashed")) button(card, "Restore from Trash", () -> restore(operation));
      if (status.equals("preview")
          || status.equals("validating")
          || status.equals("awaiting_android"))
        button(card, "Dismiss unresolved request", () -> cancel(operation));
    }
  }
}
