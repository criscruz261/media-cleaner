// Requires smoke-server.py --similar --live --append; uses temporary synthetic media only.
import { chromium } from "../frontend/node_modules/playwright-core/index.mjs";
import { readFile, writeFile } from "node:fs/promises";
const fixture = JSON.parse(await readFile(process.argv[2], "utf8"));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 850 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${fixture.port}/#token=${fixture.token}`);
  await page.getByRole("button", { name: "Scanner", exact: true }).click();
  await page.getByLabel("Folder paths · one per line").fill(fixture.media);
  await page.getByRole("button", { name: "Start scan", exact: true }).click();
  await page.getByRole("heading", { name: "3 similar photos", exact: true }).waitFor();
  const scanId = await page.evaluate(() => JSON.parse(localStorage.getItem("media-cleaner.workspace.v1")).scanId);
  const endpoint = `http://127.0.0.1:${fixture.port}/api/v1/scans/${scanId}`;
  const before = (await (await page.request.get(endpoint + "/matches")).json()).items.map(group => group.id);
  const group = page.locator(".group-card").filter({ has: page.getByRole("heading", { name: "2 exact copies", exact: true }) });
  await group.getByRole("button", { name: "Enlarge IMG_0971.png", exact: true }).click();
  const preview = page.getByRole("dialog", { name: "Group preview" });
  await preview.getByText("IMG_0971.png", { exact: true }).waitFor();
  await preview.getByText(/Scanning continues/).waitFor();
  await preview.getByRole("button", { name: "Zoom in", exact: true }).click();
  await writeFile(fixture.release, "go");
  let final;
  for (let attempt = 0; attempt < 100; attempt++) {
    final = await (await page.request.get(endpoint + "/matches")).json();
    if (final.exact_groups === 2) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (final.exact_groups !== 2) throw new Error("New group not published");
  if (JSON.stringify(final.items.slice(0, before.length).map(group => group.id)) !== JSON.stringify(before)) throw new Error("Existing groups moved when new group appeared");
  await preview.getByText("Scan complete.", { exact: true }).waitFor();
  if (!(await preview.isVisible())) throw new Error("Preview closed when matches changed");
  await preview.getByText("125%").waitFor();
  await preview.getByRole("checkbox", { name: "Select for deletion" }).check();
  await page.waitForFunction(() => !document.querySelector('[role=dialog] input')?.disabled);
  await preview.getByRole("checkbox").uncheck();
  await page.keyboard.press("Escape");
  await preview.waitFor({ state: "detached" });
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Live review passed: existing order retained, new group appended, preview/zoom retained, progress visible through completion, choices saved.");
} finally { await browser.close(); }
