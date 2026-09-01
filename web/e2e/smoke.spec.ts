import { test, expect } from "@playwright/test";

test("首页可打开并展示品牌", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("职面 AI").first()).toBeVisible();
});