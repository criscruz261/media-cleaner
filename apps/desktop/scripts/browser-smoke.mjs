// Runs only against temporary fixtures created by smoke-server.py.
import { chromium } from "../frontend/node_modules/playwright-core/index.mjs";
import { readFile, mkdir, writeFile } from "node:fs/promises";
const fixture = JSON.parse(await readFile(process.argv[2], "utf8"));
const executable =
  process.env.CHROME_PATH ??
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const browser = await chromium.launch({
  executablePath: executable,
  headless: true,
});
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1050 },
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${fixture.port}/#token=${fixture.token}`);
  await page.getByRole("heading", { name: /A little space/ }).waitFor();
  await page.getByRole("button", { name: "Scanner", exact: true }).click();
  await page.getByLabel("Folder paths · one per line").fill(fixture.media);
  await page.getByRole("button", { name: "Start scan", exact: true }).click();
  if (fixture.live) {
    await page.getByRole("heading", { name: /2 exact copies/ }).waitFor();
    if (fixture.similar)
      await page.getByRole("heading", { name: /3 similar photos/ }).waitFor();
    const saved = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("media-cleaner.workspace.v1")),
    );
    if (!saved.scanId) throw new Error("Scan selection was not saved");
    await page.reload();
    await page.getByRole("heading", { name: /2 exact copies/ }).waitFor();
    const restored = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("media-cleaner.workspace.v1")),
    );
    if (restored.scanId !== saved.scanId)
      throw new Error("Refresh replaced the active scan");
    await page.evaluate(() => localStorage.clear());
    await page.reload();
    await page.getByRole("heading", { name: /2 exact copies/ }).waitFor();
    const recovered = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("media-cleaner.workspace.v1")),
    );
    if (recovered.scanId !== saved.scanId)
      throw new Error("Server recovery lost the active scan");
    await mkdir(fixture.artifacts, { recursive: true });
    await page.screenshot({
      path: fixture.artifacts + "/live-scanner.png",
      fullPage: true,
    });
    const liveGroup = page
      .locator(".group-card")
      .filter({ has: page.getByRole("heading", { name: "2 exact copies" }) });
    await liveGroup
      .locator(".media-card")
      .filter({
        has: page.locator(".filename", { hasText: "IMG_0971 copy.png" }),
      })
      .getByRole("checkbox")
      .click();
    await liveGroup.locator(".group-actions select").selectOption("quarantine");
    await liveGroup
      .getByRole("button", { name: /Delete selected · 1/ })
      .click();
    await page
      .getByRole("heading", { name: "Dry-run cleanup preview" })
      .waitFor();
    if (
      !(await page
        .getByRole("button", { name: "Confirm cleanup" })
        .isDisabled())
    )
      throw new Error("Live cleanup bypassed confirmation");
    await page.getByRole("dialog", { name: "Review and confirm deletion" }).getByRole("checkbox").check();
    await page.getByRole("button", { name: "Confirm cleanup" }).click();
    await page
      .getByRole("heading", { name: "Cleanup completed" })
      .waitFor();
    await page.getByRole("button", { name: "Done", exact: true }).click();
    const state = await page.request.get(
      `http://127.0.0.1:${fixture.port}/api/v1/scans/${saved.scanId}`,
    );
    if ((await state.json()).status !== "running")
      throw new Error("Live cleanup stopped the scan");
    await page.getByRole("button", { name: "Scanner", exact: true }).click();
    await writeFile(fixture.release, "go");
  }
  await page.getByText("complete", { exact: true }).waitFor({ timeout: 30000 });
  // Completed Scanner cards expose the same choices and group actions as Review.
  await page
    .locator(".group-card")
    .first()
    .getByRole("checkbox")
    .first()
    .waitFor();
  await page
    .locator(".group-card")
    .first()
    .getByRole("button", { name: /Delete selected/ })
    .waitFor();
  await page.getByRole("button", { name: "Review matches" }).click();
  const group = fixture.video
    ? page.locator(".group-card").filter({
        has: page.getByRole("heading", {
          name: "2 similar videos / animations",
        }),
      })
    : fixture.similar
      ? page.locator(".group-card").filter({
          has: page.getByRole("heading", {
            name: fixture.live ? "2 similar photos" : "3 similar photos",
          }),
        })
      : page.locator(".group-card").filter({
          has: page.getByRole("heading", { name: "2 exact copies" }),
        });
  await group.waitFor();
  const boxes = group.getByRole("checkbox");
  if ((await boxes.count()) !== (fixture.similar && !fixture.live ? 3 : 2))
    throw new Error("Missing review checkboxes");
  if (fixture.video) {
    for (const box of await boxes.all())
      if (!(await box.isChecked()))
        throw new Error("Similar videos must all start kept");
    await group
      .getByRole("button", { name: "Compare videos together" })
      .click();
    const comparison = page.getByRole("dialog", {
      name: "Compare similar videos",
    });
    await comparison
      .getByRole("button", { name: "Play all from start" })
      .click();
    await page.waitForFunction(() => {
      const players = [
        ...document.querySelectorAll(".video-compare-modal video"),
      ];
      return (
        players.length === 2 &&
        players.every((video) => video.currentTime > 0 && !video.paused)
      );
    });
    await comparison.getByRole("button", { name: "Pause all" }).click();
    if (
      !(await comparison
        .locator("video")
        .evaluateAll((players) => players.every((video) => video.paused)))
    )
      throw new Error("Pause all did not pause every video");
    await comparison.getByRole("button", { name: "Reset all" }).click();
    if (
      !(await comparison
        .locator("video")
        .evaluateAll((players) =>
          players.every((video) => video.currentTime === 0),
        ))
    )
      throw new Error("Reset all did not reset every video");
    await comparison.getByRole("button", { name: "Close comparison" }).click();
    await group
      .getByRole("button", { name: /^Play / })
      .first()
      .click();
    const posterUrl = await group
      .locator("video")
      .first()
      .getAttribute("poster");
    const poster = await page.request.get(new URL(posterUrl, page.url()).href);
    if (
      poster.status() !== 200 ||
      !poster.headers()["content-type"].includes("image/jpeg")
    )
      throw new Error("Video thumbnail unavailable");
    const video = group.locator("video").first();
    await video.evaluate(async (element) => {
      element.muted = true;
      await element.play();
    });
    await page.waitForFunction(
      () => document.querySelector(".group-card video")?.currentTime > 0,
    );
    await video.evaluate((element) => element.pause());
    await group
      .locator(".media-card")
      .filter({ has: page.locator(".filename", { hasText: "reencoded.mp4" }) })
      .getByRole("checkbox")
      .click();
    await group.getByRole("button", { name: /Delete selected · 1/ }).waitFor();
    await group.locator(".evidence summary").click();
    await group.getByText(/time-spaced visual samples match/).waitFor();
    await mkdir(fixture.artifacts, { recursive: true });
    await page.screenshot({
      path: fixture.artifacts + "/video-review.png",
      fullPage: true,
    });
  } else if (fixture.similar) {
    for (const box of await boxes.all())
      if (await box.isChecked())
        throw new Error("Similar photos must start unselected for deletion");
    await group
      .locator(".media-card")
      .filter({ has: page.locator(".filename", { hasText: "resized.jpg" }) })
      .getByRole("checkbox")
      .click();
    await group.getByRole("button", { name: /Delete selected · 1/ }).waitFor();
    await group.locator(".evidence summary").click();
    await group.getByText(/Maximum pairwise pHash distance/).waitFor();
    await mkdir(fixture.artifacts, { recursive: true });
    await page.screenshot({
      path: fixture.artifacts + "/similar-review.png",
      fullPage: true,
    });
  } else {
    const original = group
      .locator(".media-card")
      .filter({ has: page.locator(".filename", { hasText: "IMG_0971.png" }) });
    if (await original.getByRole("checkbox").isChecked())
      throw new Error("Original must not be selected for deletion");
  }
  await group.locator(".group-actions select").selectOption("quarantine");
  await group.getByRole("button", { name: /Delete selected/ }).click();
  await page
    .getByRole("heading", { name: /Dry-run cleanup preview/ })
    .waitFor();
  if (fixture.similar || fixture.video)
    await page
      .getByText(
        /These media files look similar but may contain different moments or audio/,
      )
      .waitFor();
  if (
    !(await page.getByRole("button", { name: "Confirm cleanup" }).isDisabled())
  )
    throw new Error("Confirmation missing");
  await page.getByRole("dialog", { name: "Review and confirm deletion" }).getByRole("checkbox").check();
  await page.getByRole("button", { name: "Confirm cleanup" }).click();
  await page
    .getByRole("heading", { name: "Cleanup completed" })
    .waitFor();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.getByRole("button", { name: "Cleanup", exact: true }).click();
  const operation = page.locator(".operation").first();
  await operation.locator("summary").click();
  await operation.getByText("moved", { exact: false }).waitFor();
  page.once("dialog", (dialog) => dialog.accept());
  await operation
    .getByRole("button", { name: "Restore quarantined files" })
    .click();
  await page.getByText("restored", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page.getByRole("heading", { name: /A little space/ }).waitFor();
  await mkdir(fixture.artifacts, { recursive: true });
  await page.screenshot({
    path: fixture.artifacts + "/dashboard.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: fixture.artifacts + "/mobile.png",
    fullPage: true,
  });
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "Browser smoke passed: authenticated launch, scan, original selection, cleanup confirmation, quarantine and restore.",
  );
} finally {
  await browser.close();
}
