import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1440, height: 1080 },
  deviceScaleFactor: 1,
});
await page.emulateMedia({ reducedMotion: "reduce" });
async function loaded() {
  await page.locator("img").evaluateAll(async (images) => {
    for (const image of images) image.loading = "eager";
    await Promise.all(images.map(image => image.decode().catch(() => {})));
  });
}
await page.goto("http://127.0.0.1:5173");
await page
  .locator(".batch-select select")
  .selectOption({ label: "The sample collection" });
await page.waitForFunction(
  () => document.querySelectorAll(".page-card").length === 16,
);
await page.evaluate(() => document.fonts.ready);
await mkdir("../../docs/screenshots", { recursive: true });
await loaded();
await page.screenshot({
  path: "../../docs/screenshots/library.png",
  fullPage: true,
  animations: "disabled",
});
await page
  .getByRole("button", { name: "Layout clusters", exact: true })
  .click();
await page.getByRole("button", { name: "Find layout groups" }).click();
await page.locator(".cluster-group").first().waitFor();
await loaded();
await page.locator('.toast').waitFor({state:'hidden'});
await page.screenshot({
  path: "../../docs/screenshots/clusters.png",
  fullPage: true,
  animations: "disabled",
});
await page.setViewportSize({ width: 390, height: 844 });
await page.getByRole("button", { name: "Toggle navigation" }).click();
await page.getByRole("button", { name: /^Library/ }).click();
await loaded();
await page.screenshot({
  path: "../../docs/screenshots/mobile.png",
  fullPage: true,
  animations: "disabled",
});
await browser.close();
