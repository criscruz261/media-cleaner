package com.photofold.mediacleaner;

import android.app.*;
import android.content.*;
import android.os.*;
import com.photofold.matching.Matcher;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ScanService extends Service {
  static final AtomicBoolean running = new AtomicBoolean(false), paused = new AtomicBoolean(false);
  private final ExecutorService executor = Executors.newSingleThreadExecutor();
  private Store store;
  private long lastActivity;

  static final class Stopped extends RuntimeException {}

  @Override
  public void onCreate() {
    super.onCreate();
    store = ((CleanerApp) getApplication()).store;
    getSystemService(NotificationManager.class)
        .createNotificationChannel(
            new NotificationChannel("scan", "Media scanning", NotificationManager.IMPORTANCE_LOW));
  }

  private Notification notification(String text) {
    PendingIntent content =
        PendingIntent.getActivity(
            this,
            0,
            new Intent(this, MainActivity.class),
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    PendingIntent pause =
        PendingIntent.getService(
            this,
            1,
            new Intent(this, ScanService.class).setAction("pause"),
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    return new Notification.Builder(this, "scan")
        .setSmallIcon(com.photofold.mediacleaner.R.drawable.ic_cleaner)
        .setContentTitle("Media Cleaner")
        .setContentText(text)
        .setContentIntent(content)
        .setOngoing(true)
        .addAction(new Notification.Action.Builder(null, "Pause", pause).build())
        .build();
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int id) {
    if (intent != null && "pause".equals(intent.getAction())) {
      paused.set(true);
      if (!running.get()) stopSelf();
      return START_NOT_STICKY;
    }
    if (!running.compareAndSet(false, true)) return START_NOT_STICKY;
    paused.set(false);
    startForeground(1, notification("Preparing saved checkpoints…"));
    String album = intent == null ? store.meta("album", "") : intent.getStringExtra("album");
    if (album == null) album = "";
    String selected = album;
    boolean forceRescan = intent != null && intent.getBooleanExtra("force_rescan", false);
    String sensitivity =
        intent == null
            ? store.meta("scan_sensitivity", "balanced")
            : intent.getStringExtra("sensitivity");
    if (sensitivity == null) sensitivity = "balanced";
    int samples =
        intent == null
            ? Integer.parseInt(store.meta("scan_samples", "9"))
            : intent.getIntExtra("video_samples", 9);
    samples = Math.max(6, Math.min(24, samples));
    // Save the selected scope before discovery, which can itself be interrupted.
    store.prepareScan(selected, sensitivity, samples);
    final String selectedSensitivity = sensitivity;
    final int selectedSamples = samples;
    executor.submit(() -> scan(selected, forceRescan, selectedSensitivity, selectedSamples));
    return START_NOT_STICKY;
  }

  private void check() {
    if (paused.get() || Thread.currentThread().isInterrupted()) throw new Stopped();
  }

  private void activity(String text) {
    long now = SystemClock.elapsedRealtime();
    if (now - lastActivity < 250) return;
    lastActivity = now;
    store.put("activity", text);
    store.touch();
    getSystemService(NotificationManager.class).notify(1, notification(text));
  }

  private void scan(String album, boolean forceRescan, String sensitivity, int sampleCount) {
    int processed = 0, errors = 0, cached = 0;
    try {
      store.put("status", "running");
      activity("Discovering accessible photos and videos…");
      List<Media> discovered = MediaRepository.discover(this, album, this::check);
      check();
      if (forceRescan) store.invalidateAnalysis(discovered);
      store.begin(album, discovered.size());
      Matcher matcher = new Matcher(sensitivity);
      for (Media media : discovered) {
        check();
        Media old = store.file(media.uri);
        List<Matcher.Group> changed = List.of();
        try {
          if (!MediaRepository.unchanged(this, media))
            throw new IllegalStateException("Media changed or access was removed");
          if (old != null
              && old.ready
              && old.identity.equals(media.identity)
              && old.descriptor.contains(Matcher.VERSION)
              && (!media.kind.equals("video")
                  || new org.json.JSONObject(old.descriptor).optInt("sample_count", 9)
                      == sampleCount)) {
            media.digest = old.digest;
            media.descriptor = old.descriptor;
            media.warning = old.warning;
            cached++;
          } else {
            media.digest = MediaRepository.hash(this, media, this::check, this::activity);
            try {
              media.descriptor =
                  MediaRepository.describe(this, media, this::check, this::activity, sampleCount);
            } catch (Stopped stopped) {
              throw stopped;
            } catch (Exception failure) {
              media.descriptor = "{\"version\":\"" + Matcher.VERSION + "\"}";
              media.warning =
                  "Visual comparison unavailable: "
                      + failure.getClass().getSimpleName()
                      + ". Exact matching remains available.";
            }
          }
          check();
          if (!MediaRepository.unchanged(this, media))
            throw new IllegalStateException("Media changed during comparison");
          media.ready = true;
          changed = matcher.add(media.item());
        } catch (Stopped stopped) {
          throw stopped;
        } catch (Exception failure) {
          media.ready = false;
          media.warning =
              "Skipped: " + failure.getClass().getSimpleName() + ". Check access and rescan.";
          errors++;
        }
        store.save(media, changed, ++processed, errors, cached);
        activity("Saved " + processed + " / " + discovered.size() + " files");
      }
      check();
      store.recommend(matcher.groups());
      store.put("status", "completed");
      store.put("activity", "Scan complete. Compare media and choose what to keep.");
    } catch (Stopped stopped) {
      store.put("status", "paused");
      store.put(
          "activity", "Paused. Completed files are saved; Continue Scan skips unchanged media.");
    } catch (Exception failure) {
      store.put("status", "interrupted");
      store.put(
          "activity",
          "Scan interrupted: "
              + failure.getClass().getSimpleName()
              + ". Check permissions and use Continue Scan.");
    } finally {
      store.touch();
      running.set(false);
      stopForeground(STOP_FOREGROUND_REMOVE);
      stopSelf();
    }
  }

  @Override
  public void onTimeout(int startId, int fgsType) {
    paused.set(true);
    stopForeground(STOP_FOREGROUND_REMOVE);
    stopSelf();
  }

  @Override
  public void onDestroy() {
    paused.set(true);
    executor.shutdown();
    super.onDestroy();
  }

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }
}
