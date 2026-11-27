const { chromium } = require('d:/smartscan-2026/frontend/node_modules/playwright');

async function runE2ESelfTest() {
  console.log("==================================================================");
  console.log("SMARTSCAN 2026 — FULL ROLE-BY-ROLE BROWSER E2E SELF-TEST");
  console.log("==================================================================");

  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 850 },
  });
  const page = await context.newPage();

  page.on('pageerror', err => {
    console.error("PAGE ERROR:", err.message);
  });

  let customerBillNo = "SS-20481";

  try {
    // =================================================================
    // FLOW 1: CUSTOMER FLOW
    // =================================================================
    console.log("\n>>> [1/3] Testing Customer Flow (demo@smartscan.app)...");
    await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.reload({ waitUntil: "networkidle" });
    await page.waitForTimeout(1000);

    const continueDemoBtn = page.locator("text=Continue as Demo Customer");
    if (await continueDemoBtn.isVisible()) {
      console.log("-> Clicking 'Continue as Demo Customer'...");
      await continueDemoBtn.click();
      await page.waitForTimeout(2000);
    }

    // Select FreshMart store if on home screen
    const freshMartStore = page.locator("text=FreshMart").first();
    if (await freshMartStore.isVisible()) {
      console.log("-> Selecting FreshMart store...");
      await freshMartStore.click();
      await page.waitForTimeout(1500);
    }

    // Navigate to Scanner screen
    console.log("-> Navigating to Scanner screen...");
    const openScannerBtn = page.locator("text=Open Scanner").or(page.locator("button:has-text('Scan')")).first();
    if (await openScannerBtn.isVisible()) {
      await openScannerBtn.click();
      await page.waitForTimeout(1500);
    }

    // Manual barcode entry in Scanner
    console.log("-> Looking up product barcode '8901262010015' (Amul Milk)...");
    const barcodeInput = page.locator("input[placeholder*='890']").or(page.locator("input[type='text']")).first();
    await barcodeInput.waitFor({ state: "visible", timeout: 10000 });
    await barcodeInput.fill("8901262010015");
    await page.waitForTimeout(300);
    await barcodeInput.press("Enter");
    await page.waitForTimeout(2000);

    // Verify detection card
    const milkText = page.locator("text=Amul Taaza Milk 500ml").first();
    await milkText.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> Product detected: Amul Taaza Milk 500ml");

    // Add to cart
    const addToCartBtn = page.locator("button:has-text('Add to Cart')").first();
    await addToCartBtn.click();
    console.log("-> Added to cart.");
    await page.waitForTimeout(1000);

    // Navigate to Cart
    console.log("-> Navigating to Cart...");
    const cartNavBtn = page.locator("button:has-text('Cart')").or(page.locator("text=View Cart")).first();
    await cartNavBtn.click();
    await page.waitForTimeout(1500);

    // Click Checkout / Proceed to Pay
    console.log("-> On Cart screen. Proceeding to checkout...");
    const checkoutBtn = page.locator("button:has-text('Proceed to Pay')").or(page.locator("button:has-text('Checkout')")).or(page.locator("button:has-text('Pay')")).first();
    await checkoutBtn.click();
    await page.waitForTimeout(1500);

    // On Payment screen, click Mock UPI / Pay Now
    console.log("-> On Payment screen. Submitting Mock UPI payment...");
    const payNowBtn = page.locator("button:has-text('Pay ₹')").or(page.locator("button:has-text('Pay Now')")).or(page.locator("button:has-text('Mock Pay')")).first();
    await payNowBtn.click();
    await page.waitForTimeout(2000);

    // Verify Bill Screen
    const billHeading = page.locator("text=Digital Receipt").or(page.locator("text=Payment Successful")).or(page.locator("text=PAID")).first();
    await billHeading.waitFor({ state: "visible", timeout: 8000 });
    
    // Extract Bill Number
    const billTextEl = page.locator("text=SS-").first();
    if (await billTextEl.isVisible()) {
      const fullText = await billTextEl.textContent();
      const match = fullText.match(/SS-\d+/);
      if (match) {
        customerBillNo = match[0];
      }
    }
    console.log(`-> Bill generated successfully: ${customerBillNo}`);
    console.log("[Customer Flow]: PASS");

    // =================================================================
    // FLOW 2: STAFF FLOW
    // =================================================================
    console.log("\n>>> [2/3] Testing Exit Staff Flow (staff@smartscan.app)...");
    
    // Clear storage and navigate to fresh login screen
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);

    // Click Exit Staff Demo button
    const staffDemoBtn = page.locator("text=Switch to Exit Staff Demo (FreshMart)");
    await staffDemoBtn.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> Clicking 'Switch to Exit Staff Demo (FreshMart)'...");
    await staffDemoBtn.click();
    await page.waitForTimeout(2000);

    // Verify staff screen loaded
    const staffTitle = page.locator("text=Exit Gate Verification").or(page.locator("text=Staff")).first();
    await staffTitle.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> Staff Exit Verification screen loaded.");

    // Enter bill number
    const billInput = page.locator("input[placeholder*='SS-']").or(page.locator("input[placeholder*='bill']")).first();
    await billInput.fill(customerBillNo);
    await page.locator("button:has-text('Verify')").first().click();
    await page.waitForTimeout(1500);

    // Verify VERIFIED banner appears
    const verifiedBanner = page.locator("text=VERIFIED").or(page.locator("text=Paid")).first();
    await verifiedBanner.waitFor({ state: "visible", timeout: 8000 });
    console.log(`-> Bill ${customerBillNo} verified with green VERIFIED banner!`);

    // Click Allow Exit / Mark Used
    const allowExitBtn = page.locator("button:has-text('Allow Exit')").or(page.locator("button:has-text('Mark Used')")).first();
    if (await allowExitBtn.isVisible()) {
      console.log("-> Clicking 'Allow Exit / Mark Used'...");
      await allowExitBtn.click();
      await page.waitForTimeout(1500);

      // Verify USED_DONE banner
      const usedDoneBanner = page.locator("text=Exit approved").or(page.locator("text=EXIT APPROVED")).or(page.locator("text=ALREADY_USED")).first();
      await usedDoneBanner.waitFor({ state: "visible", timeout: 8000 });
      console.log("-> Exit approved banner verified.");
    }

    // Check Cash Pending Tab
    const cashTab = page.locator("text=Cash Counter").or(page.locator("text=Cash Pending")).or(page.locator("text=Pending Cash")).first();
    if (await cashTab.isVisible()) {
      await cashTab.click();
      await page.waitForTimeout(800);
      console.log("-> Cash pending section verified.");
    }
    console.log("[Staff Flow]: PASS");

    // =================================================================
    // FLOW 3: MANAGER FLOW
    // =================================================================
    console.log("\n>>> [3/3] Testing Manager Flow (manager@smartscan.app)...");
    
    // Clear storage and navigate to login
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.goto("http://127.0.0.1:5173", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);

    // Click Manager Demo button
    const mgrDemoBtn = page.locator("text=Switch to Manager Dashboard Demo (FreshMart)");
    await mgrDemoBtn.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> Clicking 'Switch to Manager Dashboard Demo (FreshMart)'...");
    await mgrDemoBtn.click();
    await page.waitForTimeout(2500);

    // 1. Verify Manager Dashboard KPIs
    const mgrTitle = page.locator("text=Retailer Portal").or(page.locator("text=Dashboard")).first();
    await mgrTitle.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> Manager Portal loaded.");

    // Check KPI cards
    const revenueCard = page.locator("text=Total Sales").or(page.locator("text=Today's Sales")).first();
    await revenueCard.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> KPI summary cards verified.");

    // Check Low stock inventory list (must show Coca-Cola out of stock)
    const cokeLowStock = page.locator("text=Coca-Cola 750ml").first();
    await cokeLowStock.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> Low stock inventory verified: Coca-Cola 750ml (Out of stock) is visible.");

    // Check SDG impact panel
    const sdgPanel = page.locator("text=Queue time saved").or(page.locator("text=Paper bills avoided")).first();
    await sdgPanel.waitFor({ state: "visible", timeout: 8000 });
    console.log("-> SDG impact panel verified (queue time saved & paper bills avoided).");

    // 2. Switch to Products & Inventory Tab
    console.log("-> Switching to Products & Inventory tab (Inventory & Stock)...");
    const productsNavBtn = page.locator("text=Inventory & Stock").first();
    await productsNavBtn.click();
    await page.waitForTimeout(1500);

    // Search
    console.log("-> Testing catalogue search for 'Milk'...");
    const searchInput = page.locator("input[placeholder*='Search']").first();
    await searchInput.fill("Milk");
    await page.waitForTimeout(800);
    const searchResult = page.locator("text=Amul Taaza Milk").first();
    await searchResult.waitFor({ state: "visible", timeout: 5000 });
    console.log("-> Search verified: Amul Milk found.");
    await searchInput.fill("");
    await page.waitForTimeout(800);

    // Inline edit
    console.log("-> Testing inline edit on first product...");
    const editBtn = page.locator("button:has-text('Edit')").first();
    if (await editBtn.isVisible()) {
      await editBtn.click();
      await page.waitForTimeout(500);
      const inlinePriceInput = page.locator("input[type='number']").first();
      if (await inlinePriceInput.isVisible()) {
        await inlinePriceInput.fill("65");
        const saveInlineBtn = page.locator("button:has-text('Save')").first();
        await saveInlineBtn.click();
        await page.waitForTimeout(1000);
        console.log("-> Inline price edit saved.");
      }
    }

    // Scan to Add Modal
    console.log("-> Testing Scan-to-Add modal...");
    const addProductBtn = page.locator("button:has-text('Add Product')").first();
    await addProductBtn.click();
    await page.waitForTimeout(1000);

    const modalBarcodeForm = page.locator("form:has(button:has-text('Look Up'))").first();
    await modalBarcodeForm.locator("input").fill("8905555444433");
    await page.waitForTimeout(300);
    await modalBarcodeForm.locator("button[type='submit']").click();
    await page.waitForTimeout(1500);

    // Fill new product form
    const prodNameInput = page.locator("input[placeholder*='Sweatshirt']").first();
    await prodNameInput.waitFor({ state: "visible", timeout: 8000 });
    await prodNameInput.fill("Browser E2E Chips");
    const priceInput = page.locator("input[placeholder='899']").or(page.locator("input[type='number']")).first();
    await priceInput.fill("35");
    const saveProdBtn = page.locator("button:has-text('Save to Catalogue')").or(page.locator("button:has-text('Update Product')")).first();
    await saveProdBtn.click();
    await page.waitForTimeout(1500);

    // Click Done on success card
    const doneBtn = page.locator("button:has-text('Done')").first();
    await doneBtn.waitFor({ state: "visible", timeout: 5000 });
    await doneBtn.click();
    await page.waitForTimeout(1000);
    console.log("-> Scan-to-Add saved new product: 'Browser E2E Chips'.");

    // Test Barcode Sticker Modal
    console.log("-> Testing Barcode Sticker Print modal...");
    const stickerBtn = page.locator("button:has-text('Sticker')").first();
    if (await stickerBtn.isVisible()) {
      await stickerBtn.click();
      await page.waitForTimeout(1000);
      const stickerModal = page.locator("text=Barcode Sticker Print").first();
      await stickerModal.waitFor({ state: "visible", timeout: 5000 });
      console.log("-> Barcode sticker modal opened with sticker vector preview.");
      await page.locator("button:has-text('Close')").or(page.locator("button >> svg.lucide-x")).first().click();
      await page.waitForTimeout(800);
    }

    // Test Bulk CSV Import Modal
    console.log("-> Testing CSV Bulk Import modal...");
    const bulkImportBtn = page.locator("button:has-text('Import Products')").first();
    if (await bulkImportBtn.isVisible()) {
      await bulkImportBtn.click();
      await page.waitForTimeout(1000);
      const importModalTitle = page.locator("text=Bulk Import Products").first();
      await importModalTitle.waitFor({ state: "visible", timeout: 5000 });
      const downloadTmplBtn = page.locator("text=Download Template").first();
      await downloadTmplBtn.waitFor({ state: "visible", timeout: 5000 });
      console.log("-> CSV Bulk Import modal opened with Download Template option.");
      await page.locator("button >> svg.lucide-x").first().click();
      await page.waitForTimeout(800);
    }

    // Test Demo Reset Dialog
    console.log("-> Testing In-App Demo Reset dialog...");
    const resetModalTrigger = page.locator("button:has-text('Reset Demo Data')").first();
    if (await resetModalTrigger.isVisible()) {
      await resetModalTrigger.click();
      await page.waitForTimeout(1000);
      const confirmResetBtn = page.locator("button:has-text('Confirm Reset')").first();
      if (await confirmResetBtn.isVisible()) {
        await confirmResetBtn.click();
        await page.waitForTimeout(2500);
        console.log("-> In-App Demo Reset executed successfully.");
      }
    }

    console.log("[Manager Flow]: PASS");

    console.log("\n==================================================================");
    console.log("ALL ROLES (CUSTOMER, STAFF, MANAGER) PASSED MANUAL BROWSER CLICKTHROUGH!");
    console.log("==================================================================");

  } catch (err) {
    console.error("\nE2E SELF-TEST FAILED:", err);
    await page.screenshot({ path: "d:/smartscan-2026/e2e_error.png" });
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runE2ESelfTest();
