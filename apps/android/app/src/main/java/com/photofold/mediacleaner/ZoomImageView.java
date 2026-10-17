package com.photofold.mediacleaner;

import android.content.Context;
import android.graphics.Matrix;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.widget.ImageView;

/** Fits an image to the available viewport, with bounded pinch zoom and drag panning. */
final class ZoomImageView extends ImageView {
  private final Matrix transform = new Matrix();
  private float zoom = 1, x, y, previousX, previousY;
  private final ScaleGestureDetector detector;

  ZoomImageView(Context context) {
    super(context);
    setScaleType(ScaleType.MATRIX);
    detector =
        new ScaleGestureDetector(
            context,
            new ScaleGestureDetector.SimpleOnScaleGestureListener() {
              @Override
              public boolean onScale(ScaleGestureDetector gesture) {
                float next = Math.max(1, Math.min(5, zoom * gesture.getScaleFactor()));
                float ratio = next / zoom;
                x = (gesture.getFocusX() - getWidth() / 2f) * (1 - ratio) + x * ratio;
                y = (gesture.getFocusY() - getHeight() / 2f) * (1 - ratio) + y * ratio;
                zoom = next;
                updateTransform();
                return true;
              }
            });
  }

  void fit() {
    zoom = 1;
    x = 0;
    y = 0;
    updateTransform();
  }

  void zoomBy(float factor) {
    zoom = Math.max(1, Math.min(5, zoom * factor));
    updateTransform();
  }

  @Override
  protected void onSizeChanged(int w, int h, int oldW, int oldH) {
    super.onSizeChanged(w, h, oldW, oldH);
    fit();
  }

  private void updateTransform() {
    if (getDrawable() == null || getWidth() == 0 || getHeight() == 0) return;
    float width = getDrawable().getIntrinsicWidth(), height = getDrawable().getIntrinsicHeight();
    float scale = Math.min(getWidth() / width, getHeight() / height) * zoom;
    float extraX = Math.max(0, (width * scale - getWidth()) / 2);
    float extraY = Math.max(0, (height * scale - getHeight()) / 2);
    x = Math.max(-extraX, Math.min(extraX, x));
    y = Math.max(-extraY, Math.min(extraY, y));
    transform.setScale(scale, scale);
    transform.postTranslate(
        (getWidth() - width * scale) / 2 + x, (getHeight() - height * scale) / 2 + y);
    setImageMatrix(transform);
  }

  @Override
  public boolean onTouchEvent(MotionEvent event) {
    detector.onTouchEvent(event);
    if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
      previousX = event.getX();
      previousY = event.getY();
    } else if (event.getActionMasked() == MotionEvent.ACTION_MOVE) {
      if (!detector.isInProgress() && event.getPointerCount() == 1) {
        x += event.getX() - previousX;
        y += event.getY() - previousY;
        updateTransform();
      }
      previousX = event.getX();
      previousY = event.getY();
    } else if (event.getActionMasked() == MotionEvent.ACTION_UP) performClick();
    return true;
  }

  @Override
  public boolean performClick() {
    super.performClick();
    return true;
  }
}
