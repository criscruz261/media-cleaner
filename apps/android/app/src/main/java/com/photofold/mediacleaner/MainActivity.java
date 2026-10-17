package com.photofold.mediacleaner;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.*;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
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
  private static final int INK = 0xff233c32,
      GREEN = 0xff315f48,
      CANVAS = 0xfff7f8f5,
      BORDER = 0xffe2e7df,
      MUTED = 0xff69786d,
      TINT = 0xffedf2e9;
  private final Map<String, ScrollView> pages = new LinkedHashMap<>();
  private final Map<String, Button> navigation = new LinkedHashMap<>();
  private String currentPage = "Dashboard";
  private TextView pageTitle,
      pageDescription,
      dashboardFiles,
      dashboardGroups,
      dashboardSimilar,
      dashboardStatus,
      dashboardCleanup;
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
  private final Map<String, LinearLayout> groupCards = new LinkedHashMap<>();
  private final Map<String, String> groupStamps = new HashMap<>();
  private final Set<String> expandedGroups = new HashSet<>();
  private final List<TextView> reviewProgress = new ArrayList<>();
  private TextView groupCount, emptyGroups;
  private Button batchDelete;
  private TextView progress, activity, access;
  private ProgressBar bar;
  private Spinner albums;
  private String groupFilter = "";
  private int groupSort = 0;
  private Button start, pause, resume;
  private String stamp = "";
  private int limit = 5;
  private boolean cleanupBusy = false;
  private boolean checkpointBusy = false;
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
    LinearLayout screen = column();
    screen.setPadding(0, 0, 0, 0);
    screen.setBackgroundColor(CANVAS);
    setContentView(screen);
    screen.setOnApplyWindowInsetsListener(
        (view, insets) -> {
          android.graphics.Insets edges = insets.getInsets(WindowInsets.Type.systemBars());
          screen.setPadding(edges.left, edges.top, edges.right, edges.bottom);
          return insets;
        });
    LinearLayout brand = column();
    brand.setPadding(dp(20), dp(10), dp(20), dp(8));
    brand.setBackgroundColor(Color.WHITE);
    TextView wordmark = label(brand, "Media Cleaner");
    wordmark.setTextSize(18);
    wordmark.setTypeface(null, Typeface.BOLD);
    screen.addView(brand);
    LinearLayout pageHeader = column();
    pageHeader.setPadding(dp(20), dp(10), dp(20), dp(4));
    pageTitle = label(pageHeader, "Dashboard");
    pageTitle.setTextSize(28);
    pageTitle.setTypeface(null, Typeface.BOLD);
    pageDescription = label(pageHeader, "Your library at a glance.");
    screen.addView(pageHeader);
    LinearLayout live = column();
    live.setPadding(dp(20), 0, dp(20), dp(6));
    progress = label(live, "");
    progress.setTextSize(12);
    progress.setMaxLines(2);
    bar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
    bar.setProgressTintList(ColorStateList.valueOf(GREEN));
    live.addView(bar);
    activity = label(live, "");
    activity.setTextSize(12);
    activity.setMaxLines(2);
    activity.setEllipsize(android.text.TextUtils.TruncateAt.END);
    screen.addView(live);
    FrameLayout content = new FrameLayout(this);
    screen.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
    for (String name : List.of("Dashboard", "Scanner", "Review", "Cleanup", "Settings")) {
      ScrollView page = new ScrollView(this);
      page.setFillViewport(true);
      LinearLayout pageBody = column();
      pageBody.setPadding(dp(16), dp(8), dp(16), dp(20));
      page.addView(pageBody);
      pages.put(name, page);
      content.addView(page, new FrameLayout.LayoutParams(-1, -1));
    }
    LinearLayout bottom = row();
    bottom.setPadding(dp(4), dp(6), dp(4), dp(6));
    bottom.setBackgroundColor(Color.WHITE);
    int[] icons = {
      R.drawable.nav_dashboard,
      R.drawable.nav_scanner,
      R.drawable.nav_review,
      R.drawable.nav_cleanup,
      R.drawable.nav_settings
    };
    int iconIndex = 0;
    for (String name : pages.keySet()) {
      Button tab = button(bottom, name, () -> switchPage(name));
      tab.setTextSize(10);
      tab.setPadding(dp(2), dp(8), dp(2), dp(8));
      tab.setMinWidth(0);
      tab.setMinimumWidth(0);
      android.graphics.drawable.Drawable icon = getDrawable(icons[iconIndex++]).mutate();
      icon.setTint(GREEN);
      icon.setBounds(0, 0, dp(22), dp(22));
      tab.setCompoundDrawables(null, icon, null, null);
      tab.setCompoundDrawablePadding(dp(4));
      navigation.put(name, tab);
    }
    screen.addView(bottom);
    LinearLayout dashboard = pageBody("Dashboard");
    LinearLayout overview = card(dashboard);
    heading(overview, "Library overview", 20);
    dashboardFiles = metric(overview, "Files scanned");
    dashboardGroups = metric(overview, "Exact duplicate groups");
    dashboardSimilar = metric(overview, "Similar media groups");
    primary(button(overview, "Start a new scan", () -> switchPage("Scanner")));
    LinearLayout recent = card(dashboard);
    heading(recent, "Recent activity", 20);
    dashboardStatus = label(recent, "");
    button(recent, "Continue reviewing", () -> switchPage("Review"));
    dashboardCleanup = label(recent, "");
    button(recent, "View cleanup history", () -> switchPage("Cleanup"));
    label(dashboard, "Private by design · All media processing stays on this device.");
    LinearLayout body = card(pageBody("Scanner"));
    heading(body, "Scan your library", 20);
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
    label(body, "Media source");
    LinearLayout actions = column();
    body.addView(actions);
    start = button(actions, "Scan", () -> start(false));
    primary(start);
    pause = button(actions, "Save checkpoint", () -> saveCheckpoint(false));
    resume = button(actions, "Resume", () -> start(true));
    button(body, "Save checkpoint and close", () -> saveCheckpoint(true));
    label(
        body,
        "Completed files and selections are saved automatically in app storage. Resume revalidates"
            + " access and reuses unchanged files. App data survives closing and rotation, but not"
            + " uninstall or Clear storage.");
    button(body, "Review matches found so far", () -> switchPage("Review"));
    body = card(pageBody("Review"));
    heading(body, "Matches found so far", 22);
    label(
        body,
        "Choose what to keep. Matches update while scanning; Android confirms every move to"
            + " Trash.");
    label(body, "Filter groups (also scopes batch deletion)");
    Spinner filter = new Spinner(this);
    filter.setAdapter(
        new ArrayAdapter<>(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            List.of("All matches", "Exact duplicates only", "Similar media only")));
    body.addView(filter);
    label(body, "Sort groups");
    Spinner sort = new Spinner(this);
    sort.setAdapter(
        new ArrayAdapter<>(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            List.of(
                "Discovery order",
                "Exact duplicates first",
                "Most recoverable space",
                "Most files")));
    body.addView(sort);
    AdapterView.OnItemSelectedListener options =
        new AdapterView.OnItemSelectedListener() {
          public void onNothingSelected(AdapterView<?> parent) {}

          public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
            groupFilter =
                switch (filter.getSelectedItemPosition()) {
                  case 1 -> "EXACT_DUPLICATE";
                  case 2 -> "SIMILAR_CONTENT";
                  default -> "";
                };
            groupSort = sort.getSelectedItemPosition();
            limit = 5;
            stamp = "";
            if (groups != null) refresh();
          }
        };
    filter.setOnItemSelectedListener(options);
    sort.setOnItemSelectedListener(options);
    label(
        body,
        "Batch cleanup includes reviewed groups across all pages of this filter. Review each"
            + " group's keeper before including it.");
    batchDelete = button(body, "Delete selected across groups", () -> preview(null));
    emptyGroups = label(body, "");
    groups = column();
    body.addView(groups);
    groupCount = label(body, "");
    button(
        body,
        "Show more groups",
        () -> {
          limit += 5;
          stamp = "";
          refresh();
        });
    body = card(pageBody("Cleanup"));
    heading(body, "Cleanup and recovery", 22);
    label(
        body,
        "Trash retention is managed by Android. Restore through this history or your gallery’s"
            + " Trash before the device removes expired items.");
    history = column();
    body.addView(history);
    LinearLayout settings = pageBody("Settings");
    LinearLayout permissions = card(settings);
    heading(permissions, "Media access", 20);
    label(
        permissions,
        "Android controls which photos and videos this app can read. Selected-only access limits"
            + " the scan to your chosen items.");
    button(permissions, "Allow / change photo and video access", this::requestAccess);
    LinearLayout storage = card(settings);
    heading(storage, "Storage and privacy", 20);
    label(
        storage,
        "Your library, checkpoints, and review selections are saved on this device. No account or"
            + " desktop server is required.");
    label(
        storage,
        "Uninstalling or clearing app storage removes saved checkpoints. Your gallery media is"
            + " managed separately by Android.");
    heading(storage, "Cleanup destination", 18);
    label(
        storage,
        "Android Trash · Review selections in the app, then confirm with Android. Retention and"
            + " restore availability depend on your device.");
    LinearLayout session = card(settings);
    heading(session, "Session", 20);
    button(session, "Save checkpoint and close", () -> saveCheckpoint(true));
    String selectedPage = state == null ? "Dashboard" : state.getString("page", "Dashboard");
    switchPage(selectedPage);
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

  @Override
  protected void onSaveInstanceState(Bundle state) {
    state.putString("page", currentPage);
    super.onSaveInstanceState(state);
  }

  private LinearLayout pageBody(String name) {
    return (LinearLayout) pages.get(name).getChildAt(0);
  }

  private void switchPage(String name) {
    if (!pages.containsKey(name)) name = "Dashboard";
    currentPage = name;
    for (Map.Entry<String, ScrollView> page : pages.entrySet())
      page.getValue().setVisibility(page.getKey().equals(name) ? View.VISIBLE : View.GONE);
    for (Map.Entry<String, Button> tab : navigation.entrySet()) {
      boolean selected = tab.getKey().equals(name);
      tab.getValue().setSelected(selected);
      tab.getValue().setBackground(surface(selected ? TINT : Color.WHITE, 0));
      tab.getValue().setTypeface(null, selected ? Typeface.BOLD : Typeface.NORMAL);
      tab.getValue().setContentDescription(tab.getKey() + (selected ? ", selected" : ""));
    }
    pageTitle.setText(name);
    pageDescription.setText(
        switch (name) {
          case "Scanner" -> "Find exact copies and similar photos and videos.";
          case "Review" -> "Compare matches and choose what to keep.";
          case "Cleanup" -> "Review cleanup history and restore from Trash.";
          case "Settings" -> "Manage access, privacy, and your session.";
          default -> "Your library at a glance.";
        });
    if (groups != null) refresh();
  }

  private GradientDrawable surface(int color, int border) {
    GradientDrawable drawable = new GradientDrawable();
    drawable.setColor(color);
    drawable.setCornerRadius(dp(12));
    if (border != 0) drawable.setStroke(dp(1), border);
    return drawable;
  }

  private LinearLayout card(LinearLayout parent) {
    LinearLayout result = column();
    result.setPadding(dp(16), dp(12), dp(16), dp(16));
    result.setBackground(surface(Color.WHITE, BORDER));
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.bottomMargin = dp(14);
    parent.addView(result, params);
    return result;
  }

  private TextView metric(LinearLayout parent, String name) {
    TextView caption = label(parent, name);
    caption.setTextColor(MUTED);
    TextView value = label(parent, "0");
    value.setTextSize(28);
    value.setTypeface(null, Typeface.BOLD);
    return value;
  }

  private void primary(Button view) {
    view.setTextColor(ColorStateList.valueOf(Color.WHITE));
    view.setBackground(
        new RippleDrawable(ColorStateList.valueOf(0xff52775f), surface(GREEN, 0), null));
  }

  private void styleMediaDialog(Dialog dialog) {
    Window window = dialog.getWindow();
    if (window == null) return;
    window.setBackgroundDrawableResource(R.color.canvas);
    window
        .getDecorView()
        .setOnApplyWindowInsetsListener(
            (view, insets) -> {
              android.graphics.Insets edges = insets.getInsets(WindowInsets.Type.systemBars());
              view.setPadding(edges.left, edges.top, edges.right, edges.bottom);
              return insets;
            });
    window.getDecorView().requestApplyInsets();
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
    view.setTextColor(INK);
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
    view.setStateListAnimator(null);
    view.setElevation(0);
    view.setTextSize(13);
    view.setTextColor(
        new ColorStateList(
            new int[][] {new int[] {-android.R.attr.state_enabled}, new int[] {}},
            new int[] {MUTED, INK}));
    view.setGravity(Gravity.CENTER);
    view.setMinHeight(dp(48));
    view.setMinimumHeight(dp(48));
    view.setPadding(dp(12), dp(10), dp(12), dp(10));
    view.setBackground(
        new RippleDrawable(ColorStateList.valueOf(TINT), surface(Color.WHITE, BORDER), null));
    view.setOnClickListener(ignored -> action.run());
    LinearLayout.LayoutParams params =
        parent.getOrientation() == LinearLayout.HORIZONTAL
            ? new LinearLayout.LayoutParams(0, -2, 1)
            : new LinearLayout.LayoutParams(-1, -2);
    params.setMargins(dp(2), dp(4), dp(2), dp(4));
    parent.addView(view, params);
    return view;
  }

  private void saveCheckpoint(boolean closeAfter) {
    if (cleanupBusy || checkpointBusy || !store.meta("pendingOperation", "").isEmpty()) {
      message("Finish or cancel the pending cleanup before saving a checkpoint or closing.");
      return;
    }
    if (closeAfter) {
      new AlertDialog.Builder(this)
          .setTitle("Save checkpoint and close?")
          .setMessage(
              "Pause scanning and save completed work before closing the app. Use Resume after"
                  + " reopening. Unfinished files will be checked again.")
          .setPositiveButton("Save and close", (dialog, which) -> awaitCheckpoint(true))
          .setNegativeButton("Cancel", null)
          .show();
    } else awaitCheckpoint(false);
  }

  private void awaitCheckpoint(boolean closeAfter) {
    checkpointBusy = true;
    ScanService.paused.set(true);
    activity.setText("Saving checkpoint; waiting for the scanner to stop…");
    io.submit(
        () -> {
          try {
            while (ScanService.running.get()) Thread.sleep(50);
            store.put("activity", "Checkpoint saved. Resume to continue from completed files.");
            store.touch();
            runOnUiThread(
                () -> {
                  checkpointBusy = false;
                  refresh();
                  if (closeAfter) {
                    stopService(new Intent(this, ScanService.class));
                    finishAndRemoveTask();
                  } else message("Checkpoint saved. You can resume now or reopen the app later.");
                });
          } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
          }
        });
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
    if (checkpointBusy) {
      message("Checkpoint is still being saved.");
      return;
    }
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
    start.setEnabled(!active && !cleanupBusy && !checkpointBusy);
    resume.setEnabled(
        !active && !cleanupBusy && !checkpointBusy && !store.meta("status", "").isEmpty());
    pause.setEnabled(active && !ScanService.paused.get() && !checkpointBusy);
    albums.setEnabled(!active && !cleanupBusy && !checkpointBusy);
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
    activity.setText(
        (active ? "Scanning continues; groups may still update. " : "")
            + store.meta("activity", "Choose media access, then Scan."));
    dashboardFiles.setText(store.meta("processed", "0"));
    dashboardGroups.setText(String.valueOf(store.groupCount("EXACT_DUPLICATE")));
    dashboardSimilar.setText(String.valueOf(store.groupCount("SIMILAR_CONTENT")));
    dashboardStatus.setText(
        total == 0
            ? "No scans yet. Start a scan to explore your library."
            : "Latest scan · " + status + " · " + done + " / " + total + " files");
    dashboardCleanup.setText(
        store.operations().isEmpty()
            ? "No cleanup activity yet."
            : store.operations().size() + " cleanup requests recorded");
    String reviewStatus =
        status
            + " · "
            + done
            + " / "
            + total
            + " files · "
            + (active ? "Groups may still update while scanning." : "Saved results.");
    for (TextView indicator : reviewProgress) indicator.setText(reviewStatus);
    batchDelete.setEnabled(!cleanupBusy);
    List<Store.Group> found = store.groups(limit, groupFilter, groupSort);
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
    emptyGroups.setVisibility(found.isEmpty() ? View.VISIBLE : View.GONE);
    emptyGroups.setText(
        active
            ? "Matches appear as soon as files are compared."
            : "No matching groups yet. Run a scan to compare accessible media.");
    Set<String> visible = new HashSet<>();
    for (Store.Group group : found) {
      visible.add(group.id());
      StringBuilder version =
          new StringBuilder(group.recommended() == null ? "" : group.recommended())
              .append(cleanupBusy);
      for (Media file : group.files())
        version
            .append(file.uri)
            .append(file.identity)
            .append(store.keep(group, file))
            .append(file.warning)
            .append(file.protection);
      if (!version.toString().equals(groupStamps.get(group.id()))) {
        LinearLayout old = groupCards.get(group.id());
        int position = old == null ? groups.getChildCount() : groups.indexOfChild(old);
        if (old != null) groups.removeView(old);
        LinearLayout card = renderGroup(group);
        groups.addView(card, position);
        groupCards.put(group.id(), card);
        groupStamps.put(group.id(), version.toString());
      }
    }
    for (String id : new ArrayList<>(groupCards.keySet())) {
      if (!visible.contains(id)) {
        groups.removeView(groupCards.remove(id));
        groupStamps.remove(id);
        expandedGroups.remove(id);
      }
    }
    for (int i = 0; i < found.size(); i++) {
      View card = groupCards.get(found.get(i).id());
      if (groups.indexOfChild(card) != i) {
        groups.removeView(card);
        groups.addView(card, i);
      }
    }
    groupCount.setText(
        "Showing " + found.size() + " of " + store.groupCount(groupFilter) + " matching groups");
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

  private LinearLayout renderGroup(Store.Group group) {
    LinearLayout card = column();
    card.setPadding(dp(12), dp(12), dp(12), dp(12));
    card.setBackground(surface(Color.WHITE, BORDER));
    LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(-1, -2);
    cardParams.bottomMargin = dp(16);
    card.setLayoutParams(cardParams);
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
            ? "Identical file contents. Review the suggested keeper before deleting copies."
            : "Similar appearance. Compare full photos and videos before choosing what to delete;"
                + " moments and audio may differ.");
    if (group.files().stream().filter(m -> m.kind.equals("video")).count() >= 2)
      button(card, "Compare similar videos", () -> compare(group.id()));
    LinearLayout members = column();
    card.addView(members);
    renderMembers(members, group, expandedGroups.contains(group.id()) ? 50 : 4);
    if (group.files().size() > 4)
      button(
          card,
          "Show all " + group.files().size() + " files",
          () -> {
            expandedGroups.add(group.id());
            members.removeAllViews();
            renderMembers(members, group, Math.min(group.files().size(), 50));
            if (group.files().size() > 50)
              label(
                  members,
                  "Showing first 50 files. Video comparison pages through the full video group.");
          });
    label(card, "Group " + group.id());
    Button approve =
        button(
            card,
            "Mark selections reviewed for batch deletion",
            () -> {
              try {
                store.approve(group.id());
                stamp = "";
                refresh();
                message("Selections reviewed. Included in batch cleanup for this filter.");
              } catch (Exception failure) {
                message(failure.getMessage());
              }
            });
    approve.setEnabled(!cleanupBusy);
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
    if (group.classification().equals("EXACT_DUPLICATE")) {
      label(card, "Keep one copy, or use Select all for deletion to keep none.");
    }
    long selected = group.files().stream().filter(file -> !store.keep(group, file)).count();
    Button delete = button(card, "Delete selected (" + selected + ")", () -> preview(group.id()));
    delete.setContentDescription(
        (group.files().stream().allMatch(file -> file.kind.equals("video"))
                ? "Delete selected videos ("
                : "Delete selected photos (")
            + selected
            + ")");
    delete.setEnabled(selected > 0 && !cleanupBusy);
    return card;
  }

  private void renderMembers(LinearLayout parent, Store.Group group, int count) {
    for (Media file : group.files().subList(0, Math.min(count, group.files().size()))) {
      selection(parent, group, file);
      thumbnail(parent, file, () -> open(group.id(), file.uri));
      label(
          parent, file.name + " · " + String.format(Locale.ROOT, "%.1f MB", file.size / 1048576.0));
      if (!file.warning.isEmpty()) label(parent, file.warning);
      if (!file.protection.isEmpty()) label(parent, file.protection);
    }
  }

  private void open(String groupId, String initialUri) {
    Store.Group original = store.group(groupId);
    if (original == null) return;
    List<Media> files = original.files();
    int[] index = {0};
    for (int i = 0; i < files.size(); i++) if (files.get(i).uri.equals(initialUri)) index[0] = i;
    Dialog dialog = new Dialog(this);
    dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
    LinearLayout body = column();
    TextView scanStatus = label(body, progress.getText() + " · Groups may update while scanning.");
    reviewProgress.add(scanStatus);
    TextView title = label(body, "");
    LinearLayout navigation = new LinearLayout(this);
    body.addView(navigation);
    Button previous = button(navigation, "Previous", () -> {});
    Button next = button(navigation, "Next", () -> {});
    button(navigation, "Close preview", dialog::dismiss);
    CheckBox selected = new CheckBox(this);
    selected.setText("Select for deletion");
    body.addView(selected);
    LinearLayout zoomControls = new LinearLayout(this);
    body.addView(zoomControls);
    FrameLayout viewport = new FrameLayout(this);
    viewport.setBackgroundColor(0xff101510);
    body.addView(viewport, new LinearLayout.LayoutParams(-1, 0, 1));
    ZoomImageView image = new ZoomImageView(this);
    image.setContentDescription("Photo preview: pinch to zoom and drag to pan");
    VideoView video = new VideoView(this);
    viewport.addView(image, new FrameLayout.LayoutParams(-1, -1));
    viewport.addView(video, new FrameLayout.LayoutParams(-1, -1, Gravity.CENTER));
    MediaController controller = new MediaController(this);
    controller.setAnchorView(viewport);
    video.setMediaController(controller);
    float[] videoZoom = {1};
    button(
        zoomControls,
        "Zoom out",
        () -> {
          image.zoomBy(.8f);
          videoZoom[0] = Math.max(1, videoZoom[0] / 1.25f);
          video.setScaleX(videoZoom[0]);
          video.setScaleY(videoZoom[0]);
        });
    button(
        zoomControls,
        "Fit to screen",
        () -> {
          image.fit();
          videoZoom[0] = 1;
          video.setScaleX(1);
          video.setScaleY(1);
        });
    button(
        zoomControls,
        "Zoom in",
        () -> {
          image.zoomBy(1.25f);
          videoZoom[0] = Math.min(5, videoZoom[0] * 1.25f);
          video.setScaleX(videoZoom[0]);
          video.setScaleY(videoZoom[0]);
        });
    Runnable render =
        () -> {
          Media file = files.get(index[0]);
          Store.Group current = store.group(groupId);
          title.setText((index[0] + 1) + " / " + files.size() + " · " + file.name);
          previous.setEnabled(index[0] > 0);
          next.setEnabled(index[0] + 1 < files.size());
          selected.setChecked(current != null && !store.keep(current, file));
          selected.setEnabled(current != null && file.protection.isEmpty() && !cleanupBusy);
          selected.setOnClickListener(
              view -> {
                try {
                  store.select(groupId, file.uri, selected.isChecked());
                } catch (Exception failure) {
                  selected.setChecked(!selected.isChecked());
                  message(failure.getMessage());
                }
              });
          video.stopPlayback();
          videoZoom[0] = 1;
          video.setScaleX(1);
          video.setScaleY(1);
          image.setImageDrawable(null);
          image.fit();
          boolean isVideo = file.kind.equals("video");
          image.setVisibility(isVideo ? View.GONE : View.VISIBLE);
          video.setVisibility(isVideo ? View.VISIBLE : View.GONE);
          if (isVideo) {
            video.setVideoURI(file.uri());
            video.setOnPreparedListener(
                player -> {
                  if (dialog.isShowing()) video.seekTo(1);
                });
            video.setOnErrorListener(
                (player, what, extra) -> {
                  message("Preview unavailable for this video format.");
                  return true;
                });
          } else {
            int requestedIndex = index[0];
            thumbnails.submit(
                () -> {
                  try {
                    Bitmap bitmap =
                        getContentResolver().loadThumbnail(file.uri(), new Size(2048, 2048), null);
                    runOnUiThread(
                        () -> {
                          if (dialog.isShowing() && index[0] == requestedIndex) {
                            image.setImageBitmap(bitmap);
                            image.fit();
                          }
                        });
                  } catch (Exception failure) {
                    runOnUiThread(
                        () -> {
                          if (dialog.isShowing() && index[0] == requestedIndex)
                            title.setText(file.name + " · Preview unavailable");
                        });
                  }
                });
          }
        };
    previous.setOnClickListener(
        view -> {
          if (index[0] > 0) {
            index[0]--;
            render.run();
          }
        });
    next.setOnClickListener(
        view -> {
          if (index[0] + 1 < files.size()) {
            index[0]++;
            render.run();
          }
        });
    dialog.setContentView(body);
    dialog.setOnDismissListener(
        ignored -> {
          video.stopPlayback();
          reviewProgress.remove(scanStatus);
          stamp = "";
          refresh();
        });
    dialog.show();
    dialog.getWindow().setLayout(-1, -1);
    styleMediaDialog(dialog);
    render.run();
  }

  private void compare(String groupId) {
    Store.Group group = store.group(groupId);
    if (group == null) return;
    List<Media> videos =
        group.files().stream()
            .filter(file -> file.kind.equals("video"))
            .collect(java.util.stream.Collectors.toList());
    Dialog dialog = new Dialog(this);
    dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
    comparison = dialog;
    ScrollView scroll = new ScrollView(this);
    LinearLayout content = column();
    scroll.addView(content);
    heading(content, "Compare similar videos", 22);
    TextView scanStatus =
        label(content, progress.getText() + " · Groups may update while scanning.");
    reviewProgress.add(scanStatus);
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
    LinearLayout comparisonShell = column();
    button(comparisonShell, "Close comparison", dialog::dismiss);
    comparisonShell.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    dialog.setContentView(comparisonShell);
    dialog.setOnDismissListener(
        ignored -> {
          for (VideoView player : players) player.stopPlayback();
          comparison = null;
          reviewProgress.remove(scanStatus);
          stamp = "";
          refresh();
        });
    dialog.show();
    dialog.getWindow().setLayout(-1, -1);
    styleMediaDialog(dialog);
  }

  private void validateExactKeepers(
      Set<String> selected, MediaRepository.Check checkpoint, boolean rehash) throws Exception {
    for (Store.Group group : store.groups(Integer.MAX_VALUE, "EXACT_DUPLICATE", 0)) {
      if (group.files().stream().noneMatch(file -> selected.contains(file.uri))) continue;
      if (store.explicitKeepNone(group)
          && group.files().stream().allMatch(file -> selected.contains(file.uri))) continue;
      boolean retained = false;
      for (Media file : group.files()) {
        checkpoint.run();
        if (selected.contains(file.uri) || !store.keep(group, file)) continue;
        if (!MediaRepository.unchanged(this, file)) continue;
        if (rehash
            && !MediaRepository.hash(this, file, checkpoint, ignored -> {}).equals(file.digest))
          continue;
        retained = true;
        break;
      }
      if (!retained)
        throw new IllegalArgumentException(
            Store.groupLabel(group)
                + ": Keep at least one verified file in this exact-duplicate group.");
    }
  }

  private void preview(String groupId) {
    if (cleanupBusy) return;
    if (!store.meta("pendingOperation", "").isEmpty()) {
      message(
          "A previous cleanup request is unresolved. Check its result or dismiss it in Cleanup and"
              + " recovery.");
      return;
    }
    final String cleanupFilter = groupFilter;
    final int cleanupSort = groupSort;
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
            List<Store.Group> requested = new ArrayList<>();
            if (groupId == null) {
              for (Store.Group candidate :
                  store.groups(Integer.MAX_VALUE, cleanupFilter, cleanupSort))
                if (store.reviewed(candidate)) requested.add(candidate);
            } else {
              Store.Group candidate = store.group(groupId);
              if (candidate == null)
                throw new IllegalArgumentException("Group changed. Rescan first.");
              requested.add(candidate);
            }
            Set<String> selectedUris = new HashSet<>();
            for (Store.Group group : requested)
              for (Media file : group.files())
                if (!store.keep(group, file)) selectedUris.add(file.uri);
            if (selectedUris.isEmpty() || selectedUris.size() > 100)
              throw new IllegalArgumentException("Choose 1–100 files per cleanup across groups.");
            List<Media> current = MediaRepository.discover(this, store.meta("album", ""), () -> {});
            validateExactKeepers(selectedUris, () -> {}, false);
            JSONArray items = new JSONArray();
            Set<String> added = new HashSet<>();
            boolean similar = false;
            for (Store.Group group : requested) {
              similar |= group.classification().equals("SIMILAR_CONTENT");
              Media keeper =
                  group.files().stream()
                      .filter(file -> store.keep(group, file) && !selectedUris.contains(file.uri))
                      .findFirst()
                      .orElse(null);
              if (keeper == null
                  && group.files().stream().anyMatch(file -> store.keep(group, file)))
                throw new IllegalArgumentException(
                    Store.groupLabel(group)
                        + ": A retained file is selected in another group. Keep it there too, or"
                        + " select the whole group.");
              for (Media file : group.files()) {
                if (store.keep(group, file) || !added.add(file.uri)) continue;
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
                        .put("group", group.id())
                        .put("name", file.name)
                        .put("identity", file.identity)
                        .put("digest", file.digest)
                        .put("keeper", keeper == null ? "" : keeper.uri)
                        .put("keeperIdentity", keeper == null ? "" : keeper.identity)
                        .put("keeperDigest", keeper == null ? "" : keeper.digest));
              }
            }
            JSONObject plan =
                new JSONObject()
                    .put("id", UUID.randomUUID().toString())
                    .put("created", System.currentTimeMillis())
                    .put("kind", "trash")
                    .put("status", "preview")
                    .put("resume", wasRunning)
                    .put("group", groupId == null ? "" : groupId)
                    .put("classification", similar ? "SIMILAR_CONTENT" : "EXACT_DUPLICATE")
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
    Set<String> displayed = new HashSet<>();
    for (int i = 0; i < items.length(); i++) {
      JSONObject item = items.optJSONObject(i);
      LinearLayout itemCard = card(body);
      heading(itemCard, item.optString("name"), 16);
      String key = item.optString("group", plan.optString("group"));
      if (displayed.add(key)) {
        Media retained = store.file(item.optString("keeper"));
        label(
            itemCard,
            retained == null
                ? "Keep none: every selected file in this group will move to Trash. No copy will"
                    + " remain in this group."
                : "Retained in this group: " + retained.name);
      }
    }
    label(
        body,
        "Selected files and any retained copies will be freshly hashed before Android"
            + " confirmation.");
    CheckBox confirmed = new CheckBox(this);
    confirmed.setText("I reviewed these files and want to move them to Trash");
    body.addView(confirmed);
    ScrollView review = new ScrollView(this);
    review.addView(body);
    AlertDialog dialog =
        new AlertDialog.Builder(this)
            .setTitle(
                plan.optString("group").isEmpty()
                    ? "Confirm cleanup across groups"
                    : "Confirm group cleanup")
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
            Set<String> selectedForCleanup = new HashSet<>();
            for (int i = 0; i < items.length(); i++)
              selectedForCleanup.add(items.getJSONObject(i).getString("uri"));
            validateExactKeepers(selectedForCleanup, notCancelled, true);
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
              Store.Group group = store.group(item.optString("group", plan.optString("group")));
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
    if (store.operations().isEmpty()) {
      heading(history, "No cleanup history yet", 18);
      label(history, "Review matches and select unwanted files to prepare your first cleanup.");
      button(history, "Review matches", () -> switchPage("Review"));
    }
    for (JSONObject operation : store.operations()) {
      LinearLayout card = card(history);
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
