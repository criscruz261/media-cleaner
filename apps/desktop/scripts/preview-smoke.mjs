// Uses only the temporary synthetic library created by smoke-server.py.
import { chromium } from "../frontend/node_modules/playwright-core/index.mjs";
import { readFile, mkdir } from "node:fs/promises";
const fixture = JSON.parse(await readFile(process.argv[2], "utf8"));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${fixture.port}/#token=${fixture.token}`);
  await page.getByRole("button", { name: "Scanner", exact: true }).waitFor();
  const handle = page.getByRole("separator", { name: "Resize sidebar" });
  const bounds = await handle.boundingBox();
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + 200);
  await page.mouse.down(); await page.mouse.move(320, bounds.y + 200); await page.mouse.up();
  if (Math.abs((await page.locator(".sidebar").boundingBox()).width - 320) > 1) throw new Error("Sidebar drag did not resize");
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  if ((await page.locator(".sidebar").boundingBox()).width !== 76) throw new Error("Sidebar did not collapse");
  await page.reload();
  await page.getByRole("button", { name: "Expand sidebar" }).click();
  if ((await page.locator(".sidebar").boundingBox()).width !== 320) throw new Error("Sidebar width was not restored");
  await handle.focus(); await page.keyboard.press("ArrowRight");
  if ((await page.locator(".sidebar").boundingBox()).width !== 336) throw new Error("Keyboard resize failed");
  await page.getByRole("button", { name: "Scanner", exact: true }).click();
  await page.getByLabel("Folder paths · one per line").fill(fixture.media);
  await page.getByRole("button", { name: "Start scan", exact: true }).click();
  const card = page.locator(".group-card").filter({ has: page.getByRole("heading", { name: "2 exact copies", exact: true }) });
  await card.waitFor();
  await card.getByRole("button", { name: "Enlarge IMG_0971.png", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Group preview" });
  await dialog.getByText("IMG_0971.png", { exact: true }).waitFor();
  await dialog.getByRole("button", { name: "Zoom in", exact: true }).click();
  await dialog.getByText("125%").waitFor();
  await dialog.getByRole("checkbox", { name: "Select for deletion" }).check();
  await page.waitForFunction(() => !document.querySelector('[role=dialog] input')?.disabled);
  await dialog.getByRole("checkbox").uncheck();
  await page.waitForFunction(() => !document.querySelector('[role=dialog] input')?.disabled);
  await dialog.getByRole("button", { name: "Previous", exact: true }).click();
  await dialog.getByText("IMG_0971 copy.png", { exact: true }).waitFor();
  await dialog.getByText("100%").waitFor();
  for (const size of [{ width: 1440, height: 900 }, { width: 980, height: 720 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size);
    const box = await dialog.boundingBox();
    if (box.x < 0 || box.y < 0 || box.x + box.width > size.width + 1 || box.y + box.height > size.height + 1) throw new Error("Preview exceeds viewport");
    const stage = await page.locator(".group-preview-media").boundingBox();
    if (stage.height < 100) throw new Error("No space left for preview media");
  }
  await mkdir(fixture.artifacts, { recursive: true });
  await page.screenshot({ path: fixture.artifacts + "/group-preview-mobile.png" });
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.screenshot({ path: fixture.artifacts + "/resizable-sidebar.png" });
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Preview browser check passed: sidebar resize/collapse/persistence, group navigation, zoom/reset, selection, responsive fit, Escape.");
} finally { await browser.close(); }
