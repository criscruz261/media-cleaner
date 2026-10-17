// Requires smoke-server.py --similar --live; all media and app data are temporary fixtures.
import { chromium } from "../frontend/node_modules/playwright-core/index.mjs";
import { readFile } from "node:fs/promises";
const fixture = JSON.parse(await readFile(process.argv[2], "utf8"));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${fixture.port}/#token=${fixture.token}`);
  await page.getByRole("button", {name: "Scanner", exact: true}).click();
  await page.getByLabel("Folder paths · one per line").fill(fixture.media);
  await page.getByRole("button", {name: "Start scan", exact: true}).click();
  await page.getByRole("heading", {name: "3 similar photos", exact: true}).waitFor();
  await page.getByRole("button", {name: "Pause & save checkpoint", exact: true}).click();
  await page.getByRole("button", {name: "Resume from checkpoint", exact: true}).click();
  await page.getByRole("button", {name: "Pause & save checkpoint", exact: true}).waitFor();
  const card = page.locator(".group-card").filter({ has: page.getByRole("heading", {name: "2 exact copies", exact: true}) });
  const member = card.locator(".media-card").filter({has: page.locator(".filename", {hasText: "IMG_0971 copy.png"})});
  await member.getByRole("checkbox").click();
  await card.locator(".group-actions select").selectOption("quarantine");
  await card.getByRole("button", {name: /Delete selected · 1/}).click();
  const dialog = page.getByRole("dialog", {name: "Review and confirm deletion"});
  await dialog.waitFor();
  if (!(await dialog.getByRole("button", {name: "Confirm cleanup"}).isDisabled())) throw new Error("Missing confirmation guard");
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", {name: "Confirm cleanup"}).click();
  await dialog.getByRole("heading", {name: "Cleanup completed"}).waitFor();
  await dialog.getByRole("button", {name: "Done"}).click();
  await page.getByRole("heading", {name: "Matches found so far", exact: true}).waitFor();
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem("media-cleaner.workspace.v1")));
  if (saved.page !== "Scanner") throw new Error("Group cleanup navigated away from results");
  await page.getByRole("button", {name: "Shut down safely", exact: true}).click();
  const shutdown = page.getByRole("dialog", {name: "Save checkpoint and shut down"});
  if (!(await shutdown.getByRole("button", {name: "Confirm shutdown"}).isDisabled())) throw new Error("Missing shutdown confirmation");
  await shutdown.getByRole("checkbox").check();
  await shutdown.getByRole("button", {name: "Confirm shutdown"}).click();
  await page.getByRole("heading", {name: "App safely stopped"}).waitFor();
  let stopped = false;
  for (let attempt = 0; attempt < 50; attempt++) {
    try { await page.request.get(`http://127.0.0.1:${fixture.port}/api/v1/health`, {timeout: 500}); }
    catch { stopped = true; break; }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!stopped) throw new Error("Backend process did not stop");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Checkpoint, resume, in-place group cleanup and confirmed frontend/backend shutdown passed.");
} finally { await browser.close(); }
