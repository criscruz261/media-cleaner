package com.photofold.matching;

import static org.junit.Assert.*;

import java.util.*;
import org.junit.Test;

public class MatcherTest {
  Matcher.Signature sig(long p) {
    return new Matcher.Signature(p, 0, 1.5, 100, 100, 100);
  }

  Matcher.Item photo(String id, String name, String digest, long p) {
    return new Matcher.Item(id, name, 100, digest, "image", sig(p), List.of(), 0);
  }

  @Test
  public void exactAndSimilarAreDistinctAndOriginalIsSuggested() {
    Matcher matcher = new Matcher();
    matcher.add(photo("a", "IMG.jpg", "same", 0));
    matcher.add(photo("b", "IMG copy.jpg", "same", 0));
    assertEquals(1, matcher.groups().size());
    assertEquals("a", Matcher.original(matcher.groups().get(0)));
    matcher.add(photo("c", "resized.jpg", "different", 1));
    assertEquals(2, matcher.groups().size());
    matcher.add(photo("c", "resized.jpg", "different", 1));
    assertEquals(3, matcher.groups().get(1).items.size());
  }

  @Test
  public void completeLinkRejectsWeakChains() {
    Matcher matcher = new Matcher();
    matcher.add(photo("a", "a", "a", 0));
    matcher.add(photo("b", "b", "b", 255));
    matcher.add(photo("c", "c", "c", 65535));
    assertEquals(1, matcher.groups().size());
    assertEquals(2, matcher.groups().get(0).items.size());
  }

  @Test
  public void staticVideoCannotEstablishSimilarity() {
    List<Matcher.Frame> frames = new ArrayList<>();
    for (int i = 0; i < 9; i++) frames.add(new Matcher.Frame(i, sig(1)));
    Matcher.Item a = new Matcher.Item("a", "a", 100, "a", "video", null, frames, 3);
    Matcher.Item b = new Matcher.Item("b", "b", 100, "b", "video", null, frames, 3);
    assertFalse(Matcher.compatible(a, b));
  }

  @Test
  public void sequenceRequiresDurationAndMostSamples() {
    List<Matcher.Frame> frames = new ArrayList<>();
    for (int i = 0; i < 9; i++) frames.add(new Matcher.Frame(i, sig(1L << i)));
    Matcher.Item a = new Matcher.Item("a", "a", 100, "a", "video", null, frames, 3);
    assertTrue(
        Matcher.compatible(a, new Matcher.Item("b", "b", 50, "b", "video", null, frames, 3.1)));
    assertFalse(
        Matcher.compatible(a, new Matcher.Item("b", "b", 50, "b", "video", null, frames, 4)));
  }

  @Test
  public void lowDetailImagesAreSkipped() {
    assertNull(Matcher.fingerprint(new int[1024], new int[72], 1));
  }
}
