package com.photofold.matching;

import java.util.*;
import java.util.regex.Pattern;

/** Platform-independent, conservative complete-link media matching. */
public final class Matcher {
  public static final String VERSION = "android-phash-dhash-v1";
  public static final int SAMPLE_COUNT = 9;

  public record Signature(
      long phash, long dhash, double aspect, double red, double green, double blue) {
    public boolean compatible(Signature other) {
      return Long.bitCount(phash ^ other.phash) <= 8
          && Long.bitCount(dhash ^ other.dhash) <= 10
          && Math.abs(Math.log(aspect / other.aspect)) <= 0.1
          && Math.max(
                  Math.abs(red - other.red),
                  Math.max(Math.abs(green - other.green), Math.abs(blue - other.blue)))
              <= 60;
    }
  }

  public record Frame(int slot, Signature signature) {}

  public record Item(
      String id,
      String name,
      long size,
      String digest,
      String kind,
      Signature photo,
      List<Frame> frames,
      double duration) {}

  public static final class Group {
    public final String id, classification;
    public final List<Item> items = new ArrayList<>();

    Group(String id, String classification) {
      this.id = id;
      this.classification = classification;
    }

    public boolean visible() {
      return items.size() > 1
          && (classification.equals("EXACT_DUPLICATE")
              || items.stream().map(Item::digest).distinct().count() > 1);
    }
  }

  private final Map<String, Group> exact = new LinkedHashMap<>();
  private final Map<String, Group> similar = new LinkedHashMap<>();
  private final Tree photos = new Tree();
  private final Map<Integer, Tree> sequences = new HashMap<>();
  private final Set<String> seen = new HashSet<>();

  public List<Group> add(Item item) {
    if (!seen.add(item.id) || item.digest == null) return List.of();
    List<Group> changed = new ArrayList<>();
    String key = item.size + ":" + item.digest;
    Group binary =
        exact.computeIfAbsent(key, ignored -> new Group("exact:" + key, "EXACT_DUPLICATE"));
    binary.items.add(item);
    changed.add(binary);
    boolean sequence = item.kind.equals("video");
    if ((!sequence && item.photo == null) || (sequence && !informative(item))) return changed;
    Set<String> candidates = new LinkedHashSet<>();
    if (sequence) {
      for (Frame frame : item.frames) {
        Tree tree = sequences.get(frame.slot);
        if (tree != null) tree.search(frame.signature.phash, 8, candidates);
      }
    } else photos.search(item.photo.phash, 8, candidates);
    Group target = null;
    for (String id : candidates) {
      Group group = similar.get(id);
      if (group.items.stream().allMatch(other -> compatible(item, other))) {
        target = group;
        break;
      }
    }
    if (target == null) {
      target = new Group("similar:" + item.kind + ":" + item.id, "SIMILAR_CONTENT");
      similar.put(target.id, target);
      if (sequence)
        for (Frame frame : item.frames)
          sequences
              .computeIfAbsent(frame.slot, ignored -> new Tree())
              .add(frame.signature.phash, target.id);
      else photos.add(item.photo.phash, target.id);
    }
    target.items.add(item);
    changed.add(target);
    return changed;
  }

  public static boolean informative(Item item) {
    return item.duration > 0
        && Double.isFinite(item.duration)
        && item.frames != null
        && item.frames.size() >= 6
        && item.frames.stream()
                .map(frame -> List.of(frame.signature.phash, frame.signature.dhash))
                .distinct()
                .count()
            >= 2;
  }

  public static boolean compatible(Item left, Item right) {
    if (!left.kind.equals(right.kind)) return false;
    if (!left.kind.equals("video"))
      return left.photo != null && right.photo != null && left.photo.compatible(right.photo);
    if (!informative(left)
        || !informative(right)
        || Math.abs(left.duration - right.duration)
            > Math.max(0.25, Math.min(left.duration, right.duration) * 0.03)) return false;
    int common = 0, matched = 0;
    Set<String> distinct = new HashSet<>();
    for (Frame a : left.frames)
      for (Frame b : right.frames)
        if (a.slot == b.slot) {
          common++;
          if (a.signature.compatible(b.signature)) {
            matched++;
            distinct.add(a.signature.phash + ":" + a.signature.dhash);
          }
        }
    return common >= 6
        && matched >= Math.max(6, (int) Math.ceil(common * 0.8))
        && distinct.size() >= 2;
  }

  public List<Group> groups() {
    List<Group> result = new ArrayList<>();
    for (Group group : exact.values()) if (group.visible()) result.add(group);
    for (Group group : similar.values()) if (group.visible()) result.add(group);
    return result;
  }

  private static final Pattern COPY =
      Pattern.compile("(?i)(\\bcopy\\b|\\(\\d+\\)|[_ -]copy(?:[_ -]|\\.|$))");

  public static String original(Group group) {
    if (!group.classification.equals("EXACT_DUPLICATE")) return null;
    List<Item> originals =
        group.items.stream()
            .filter(item -> !COPY.matcher(item.name).find())
            .collect(java.util.stream.Collectors.toList());
    return originals.size() == 1 ? originals.get(0).id : null;
  }

  private static final class Tree {
    private Node root;

    private static final class Node {
      long value;
      Set<String> groups = new LinkedHashSet<>();
      Map<Integer, Node> children = new HashMap<>();

      Node(long value, String id) {
        this.value = value;
        groups.add(id);
      }
    }

    void add(long value, String id) {
      if (root == null) {
        root = new Node(value, id);
        return;
      }
      Node node = root;
      while (true) {
        int d = Long.bitCount(node.value ^ value);
        if (d == 0) {
          node.groups.add(id);
          return;
        }
        Node child = node.children.get(d);
        if (child == null) {
          node.children.put(d, new Node(value, id));
          return;
        }
        node = child;
      }
    }

    void search(long value, int radius, Set<String> found) {
      if (root == null) return;
      Deque<Node> pending = new ArrayDeque<>();
      pending.add(root);
      while (!pending.isEmpty()) {
        Node node = pending.removeLast();
        int d = Long.bitCount(value ^ node.value);
        if (d <= radius) found.addAll(node.groups);
        for (Map.Entry<Integer, Node> edge : node.children.entrySet())
          if (edge.getKey() >= d - radius && edge.getKey() <= d + radius)
            pending.add(edge.getValue());
      }
    }
  }

  private static double gray(int pixel) {
    return ((pixel >> 16) & 255) * 0.299 + ((pixel >> 8) & 255) * 0.587 + (pixel & 255) * 0.114;
  }

  /** Inputs are an EXIF-oriented 32x32 bitmap and a 9x8 bitmap, in ARGB order. */
  public static Signature fingerprint(int[] pixels, int[] gradient, double aspect) {
    if (pixels.length != 1024 || gradient.length != 72 || !Double.isFinite(aspect) || aspect <= 0)
      throw new IllegalArgumentException("Invalid image dimensions");
    double[] gray = new double[1024];
    double mean = 0, variance = 0, r = 0, g = 0, b = 0;
    for (int i = 0; i < 1024; i++) {
      gray[i] = gray(pixels[i]);
      mean += gray[i];
      r += (pixels[i] >> 16) & 255;
      g += (pixels[i] >> 8) & 255;
      b += pixels[i] & 255;
    }
    mean /= 1024;
    for (double value : gray) variance += (value - mean) * (value - mean);
    if (Math.sqrt(variance / 1024) < 8) return null;
    double[][] intermediate = new double[8][32];
    double[] low = new double[64];
    for (int u = 0; u < 8; u++)
      for (int y = 0; y < 32; y++)
        for (int x = 0; x < 32; x++)
          intermediate[u][y] += gray[y * 32 + x] * Math.cos(Math.PI * (2 * x + 1) * u / 64);
    for (int v = 0; v < 8; v++)
      for (int u = 0; u < 8; u++)
        for (int y = 0; y < 32; y++)
          low[v * 8 + u] += intermediate[u][y] * Math.cos(Math.PI * (2 * y + 1) * v / 64);
    double[] sorted = low.clone();
    Arrays.sort(sorted);
    double median = (sorted[31] + sorted[32]) / 2;
    long p = 0, d = 0;
    for (double value : low) p = (p << 1) | (value > median ? 1 : 0);
    for (int y = 0; y < 8; y++)
      for (int x = 0; x < 8; x++)
        d = (d << 1) | (gray(gradient[y * 9 + x + 1]) > gray(gradient[y * 9 + x]) ? 1 : 0);
    return new Signature(p, d, aspect, r / 1024, g / 1024, b / 1024);
  }
}
