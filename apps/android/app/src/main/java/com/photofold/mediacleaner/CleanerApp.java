package com.photofold.mediacleaner;

import android.app.Application;

public final class CleanerApp extends Application {
  Store store;

  @Override
  public void onCreate() {
    super.onCreate();
    store = new Store(this);
    store.recover();
  }
}
