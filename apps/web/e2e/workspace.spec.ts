import { test, expect } from "@playwright/test";

test("sample collection, visual search, duplicate review and layout clustering", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  const seed = await request.post("http://127.0.0.1:8000/v1/demo");
  expect(seed.ok()).toBeTruthy();
  await expect(
    page.locator(".batch-select select option", {
      hasText: "The sample collection",
    }),
  ).toHaveCount(1, { timeout: 15000 });
  await page
    .locator(".batch-select select")
    .selectOption({ label: "The sample collection" });
  await expect(page.locator(".page-card")).toHaveCount(16, { timeout: 90000 });
  await page.locator(".page-card").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.locator(".similar-list button")).toHaveCount(5);
  await page.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Duplicates", exact: true }).click();
  await expect(page.locator(".pair-card").first()).toBeVisible({
    timeout: 90000,
  });
  await page.locator(".pair-card").first().click();
  await expect(page.locator(".compare-grid img")).toHaveCount(2);
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Layout clusters", exact: true })
    .click();
  await page.getByRole("button", { name: "Find layout groups" }).click();
  await expect(page.locator(".cluster-group")).toHaveCount(3, {
    timeout: 30000,
  });
  page.once("dialog", (dialog) => dialog.accept("Reviewed group"));
  await page.getByRole("button", { name: "Rename" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Reviewed group" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Pipeline", exact: true }).click();
  await expect(page.locator("tbody tr")).toHaveCount(16);
  expect(errors).toEqual([]);
});

test("mobile library and upload dialog are accessible without overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Upload documents" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("browser uploads real bytes and surfaces server-side validation failures", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const library = await request.get("http://127.0.0.1:8000/v1/pages");
  const source = (await library.json()).pages[0];
  const image = await request.get(
    "http://127.0.0.1:8000" + source.thumbnail_url,
  );
  await page.getByRole("button", { name: "Upload documents" }).click();
  await page.locator("input[type=file]").setInputFiles([
    {
      name: "interview-upload.png",
      mimeType: "image/png",
      buffer: await image.body(),
    },
    {
      name: "invalid-scan.png",
      mimeType: "image/png",
      buffer: Buffer.from("not a PNG"),
    },
  ]);
  await expect(
    page.getByRole("button", { name: "View collection" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View collection" }).click();
  await expect(page.locator(".page-card")).toHaveCount(1, { timeout: 30000 });
  await page.getByRole("button", { name: "Pipeline", exact: true }).click();
  await expect(page.locator(".job-state.failed")).toHaveCount(1, {
    timeout: 30000,
  });
  await expect(page.locator(".job-error")).toContainText(
    "File content does not match PNG",
  );
});
