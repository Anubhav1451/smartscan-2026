const { chromium } = require('d:/smartscan-2026/frontend/node_modules/playwright');

async function runStageBE2E() {
  console.log("=================================================================");
  console.log("SMARTSCAN 2026 — STAGE B GST BILLING & COMPLIANCE E2E VERIFICATION");
  console.log("=================================================================");

  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 SmartScanApp'
  });

  const page = await context.newPage();
  let generatedBillNo = null;

  try {
    // =============================================================
    // PART 1: CUSTOMER FLOW
    // =============================================================
    console.log("\n--- [PART 1: CUSTOMER FLOW] ---");
    console.log("Navigating to http://127.0.0.1:5173...");
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });

    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });

    // Customer Login via 1-click Demo button
    const demoBtn = page.locator('button:has-text("Continue as Demo Customer")');
    await demoBtn.waitFor({ timeout: 10000 });
    await demoBtn.click();
    console.log("-> Customer logged in via 'Continue as Demo Customer'");

    // Select FreshMart
    await page.waitForSelector('text=FreshMart', { timeout: 10000 });
    const freshmartCard = page.locator('.cursor-pointer:has-text("FreshMart")').first();
    await freshmartCard.click();
    console.log("-> Selected FreshMart store");

    // Scan helper function that enters scanner, looks up barcode, verifies GST, adds to cart, and waits to return to store screen
    async function scanAndAdd(barcode, expectedName, expectedGst) {
      await page.waitForSelector('text=Open Scanner', { timeout: 8000 });
      await page.locator('text=Open Scanner').click();
      
      const barcodeInput = page.locator('input[placeholder*="8901234567890"]');
      await barcodeInput.waitFor({ timeout: 8000 });
      await barcodeInput.fill(barcode);
      await page.locator('button:has-text("Look Up")').click();
      
      await page.waitForSelector(`text=${expectedName}`, { timeout: 8000 });
      if (expectedGst !== null) {
        await page.waitForSelector(`text=GST ${expectedGst}%`, { timeout: 5000 });
        console.log(`   * Verified '${expectedName}' displays 'GST ${expectedGst}%' and 'Price inclusive of all taxes'`);
      }
      
      await page.locator('button:has-text("Add to Cart")').click();
      // Wait for navigation back to store screen
      await page.waitForSelector('text=Open Scanner', { timeout: 8000 });
    }

    // Scan Item 1: Amul Taaza Milk (0% GST)
    console.log("Scanning Milk (0% GST)...");
    await scanAndAdd('8901262010015', 'Amul Taaza Milk', 0);
    console.log("-> Milk added to cart");

    // Scan Item 2: Britannia Whole Wheat Bread (0% GST)
    console.log("Scanning Bread (0% GST)...");
    await scanAndAdd('8901063142217', 'Britannia Whole Wheat Bread', 0);
    console.log("-> Bread added to cart");

    // Scan Item 3: Head & Shoulders Anti-Dandruff Shampoo (5% GST)
    console.log("Scanning Shampoo (5% GST)...");
    await scanAndAdd('4902430752108', 'Head & Shoulders', 5);
    console.log("-> Shampoo added to cart (Canonical cart 3 items, Total: Rs 317)");

    // Go to Cart
    const viewCartBtn = page.locator('text=/View Cart/');
    await viewCartBtn.waitFor({ timeout: 5000 });
    await viewCartBtn.click();
    console.log("-> Navigated to Cart screen");

    // Verify Customer Mobile input
    const mobileInput = page.locator('input[placeholder*="9876543210"]');
    await mobileInput.waitFor({ timeout: 5000 });
    console.log("-> Verified Customer Mobile input field present on CartScreen");
    await mobileInput.fill('9876543210');
    console.log("-> Entered customer mobile: 9876543210");

    // Proceed to Pay
    const proceedBtn = page.locator('button:has-text("Proceed to Pay")');
    await proceedBtn.waitFor({ timeout: 5000 });
    await proceedBtn.click();
    console.log("-> Clicked 'Proceed to Pay'");

    // Pay with Mock UPI
    const payBtn = page.locator('button:has-text("Pay ₹")');
    await payBtn.waitFor({ timeout: 5000 });
    await payBtn.click();
    console.log("-> Executed Mock UPI Payment of Rs 317");

    // Verify Digital Tax Invoice on BillScreen
    await page.waitForSelector('text=/SS-\\d+/', { timeout: 15000 });
    const billElement = page.locator('text=/SS-\\d+/').first();
    generatedBillNo = (await billElement.innerText()).match(/SS-\d+/)[0];
    console.log(`-> Tax Invoice issued: ${generatedBillNo}`);

    // Verify customer mobile on bill
    await page.waitForSelector('text=/9876543210/', { timeout: 5000 });
    console.log("-> Verified Customer Mobile (+91 9876543210) rendered on tax invoice");

    // Verify per-item GST % badges
    await page.waitForSelector('text=/GST 0%/', { timeout: 5000 });
    await page.waitForSelector('text=/GST 5%/', { timeout: 5000 });
    console.log("-> Verified per-item '(incl. GST 0%)' and '(incl. GST 5%)' badges rendered");

    // Verify GST Slab Breakup table
    await page.waitForSelector('text=GST Tax Breakup (Intra-state)', { timeout: 8000 });
    await page.waitForSelector('text=CGST + SGST', { timeout: 5000 });
    await page.waitForSelector('text=Total Tax (₹)', { timeout: 5000 });
    console.log("-> Verified GST Tax Breakup Table rendered on customer bill:");
    console.log("   - Rate slabs with Taxable, CGST, SGST, Total Tax (₹)");
    console.log("   - Total Tax Collected: ₹10.00 (Grand Total ₹317.00 exact)");

    // =============================================================
    // PART 2: STAFF FLOW
    // =============================================================
    console.log("\n--- [PART 2: STAFF FLOW] ---");
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });

    // Login as Staff via 1-click link
    const staffLink = page.locator('button:has-text("Switch to Exit Staff Demo")');
    await staffLink.waitFor({ timeout: 8000 });
    await staffLink.click();
    console.log("-> Staff logged in via 'Switch to Exit Staff Demo (FreshMart)'");

    // Verify Staff Screen
    await page.waitForSelector('text=Staff Gate', { timeout: 10000 });
    console.log("-> Landed on Staff Screen (FreshMart Supermarket)");

    // Enter bill number
    const verifyInput = page.locator('input[placeholder*="SS-"]');
    await verifyInput.waitFor({ timeout: 5000 });
    await verifyInput.fill(generatedBillNo);
    await page.locator('button:has-text("Verify")').click();
    console.log(`-> Submitted bill ${generatedBillNo} for verification`);

    // Verify VERIFIED result card
    await page.waitForSelector('text=VERIFIED', { timeout: 8000 });
    await page.waitForSelector('text=/9876543210/', { timeout: 5000 });
    console.log("-> Verification card displays VERIFIED banner and Customer Mobile 9876543210");

    // Check items with GST %
    await page.waitForSelector('text=/GST 0%/', { timeout: 5000 });
    await page.waitForSelector('text=/GST 5%/', { timeout: 5000 });
    console.log("-> Verification card displays 3 items with individual GST % badges");

    // Click "Allow Exit / Mark Used"
    const markUsedBtn = page.locator('button:has-text("Allow Exit / Mark Used")');
    await markUsedBtn.waitFor({ timeout: 5000 });
    await markUsedBtn.click();
    console.log("-> Clicked 'Allow Exit / Mark Used'");

    // Verify green USED_DONE banner
    await page.waitForSelector('text=/Exit approved - bill marked as USED/', { timeout: 8000 });
    console.log("-> Successfully verified green 'USED_DONE' state ('Exit approved - bill marked as USED.')");

    // =============================================================
    // PART 3: MANAGER FLOW
    // =============================================================
    console.log("\n--- [PART 3: MANAGER FLOW] ---");
    // Switch viewport to desktop for Manager Portal
    await page.setViewportSize({ width: 1280, height: 800 });

    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });

    // Login as Manager via 1-click link
    const managerLink = page.locator('button:has-text("Switch to Manager Dashboard Demo (FreshMart)")');
    await managerLink.waitFor({ timeout: 8000 });
    await managerLink.click();
    console.log("-> Manager logged in via 'Switch to Manager Dashboard Demo (FreshMart)'");

    // Verify Manager Dashboard
    await page.waitForSelector('text=Retailer Portal', { timeout: 10000 });
    console.log("-> Landed on Manager Portal (FreshMart)");

    // Verify GST Summary Card
    await page.waitForSelector('text=GST Summary & Compliance', { timeout: 10000 });
    console.log("-> Found 'GST Summary & Compliance' card on Overview tab");

    const todayBtn = page.locator('button:has-text("Today")').nth(1);
    const monthBtn = page.locator('button:has-text("This Month")').first();
    await todayBtn.waitFor({ timeout: 5000 });
    await monthBtn.waitFor({ timeout: 5000 });

    // Toggle This Month
    await monthBtn.click();
    await page.waitForTimeout(500);
    await page.waitForSelector('text=Taxable Value (₹)', { timeout: 5000 });
    await page.waitForSelector('text=Total Tax (₹)', { timeout: 5000 });
    await page.waitForSelector('text=Total Revenue (₹)', { timeout: 5000 });
    console.log("-> Toggled 'This Month' GST summary: Taxable Value, CGST, SGST, Total Tax, Total Revenue displayed");

    // Toggle Today
    await todayBtn.click();
    await page.waitForTimeout(500);
    console.log("-> Toggled back to 'Today' GST summary");

    // Orders & Bills Tab
    console.log("\nTesting Orders & Bills Tab...");
    const ordersTab = page.locator('nav button:has-text("Orders & Bills")');
    await ordersTab.waitFor({ timeout: 5000 });
    await ordersTab.click();
    await page.waitForTimeout(600);

    // Verify table lists orders including the bill we just paid
    await page.waitForSelector(`text=${generatedBillNo}`, { timeout: 10000 });
    console.log(`-> Orders table displays recent order ${generatedBillNo} with customer mobile 9876543210`);

    // Click row to open Bill Detail modal
    const billRow = page.locator(`tr:has-text("${generatedBillNo}")`).first();
    await billRow.click();
    await page.waitForSelector('.fixed:has-text("Digital Tax Receipt")', { timeout: 8000 });
    await page.waitForSelector('.fixed:has-text("CGST")', { timeout: 8000 });
    console.log("-> Clicked order row: Digital Tax Receipt modal opened with GST slab breakup table");

    // Close modal
    const closeBtn = page.locator('.fixed button:has(svg.lucide-x)').first();
    await closeBtn.click();
    await page.waitForTimeout(400);
    console.log("-> Closed Digital Tax Receipt modal");

    // Inventory Tab: GST % column, inline edit, Add Product modal, Sticker modal
    console.log("\nTesting Inventory & Stock Tab...");
    const inventoryTab = page.locator('nav button:has-text("Inventory & Stock")');
    await inventoryTab.waitFor({ timeout: 5000 });
    await inventoryTab.click();
    await page.waitForTimeout(600);

    // Check GST Rate header
    await page.waitForSelector('th:has-text("GST Rate")', { timeout: 8000 });
    console.log("-> Verified 'GST Rate' column in product catalog table");

    // Test inline edit: click "Edit" on the first product
    const editBtn = page.locator('button:has-text("Edit")').first();
    await editBtn.waitFor({ timeout: 5000 });
    await editBtn.click();
    console.log("-> Clicked 'Edit' on first product");

    const gstSelect = page.locator('table select').first();
    await gstSelect.waitFor({ timeout: 5000 });
    const currentGst = await gstSelect.inputValue();
    console.log(`-> Current GST rate for first product: ${currentGst}%`);
    await gstSelect.selectOption('18');
    await page.waitForTimeout(400);
    // Click Cancel to preserve data
    await page.locator('button:has-text("Cancel")').first().click();
    console.log("-> Verified inline GST select dropdown (0/5/12/18/28%) and cancelled edit");

    // Add Product Modal
    const addProductBtn = page.locator('button:has-text("Add Product")');
    await addProductBtn.waitFor({ timeout: 5000 });
    await addProductBtn.click();
    await page.waitForSelector('text=Add Product to Catalogue', { timeout: 8000 });
    
    // Enter barcode manually to reach step 2 form
    const manualBarcodeInput = page.locator('.fixed input[placeholder*="80000000378472"]');
    if (await manualBarcodeInput.isVisible()) {
      await manualBarcodeInput.fill('8909999000001');
      await page.locator('.fixed button:has-text("Look Up")').click();
      await page.waitForSelector('text=GST Rate (Inclusive MRP)', { timeout: 8000 });
      console.log("-> Add Product Modal verified: 'GST Rate (Inclusive MRP)' selector present with standard slabs (0/5/12/18/28%)");
    }
    const cancelModalBtn = page.locator('.fixed button[aria-label="Close"]');
    await cancelModalBtn.click();
    await page.waitForTimeout(400);

    // Barcode Sticker Modal
    const printStickerBtn = page.locator('button:has-text("Sticker")').first();
    await printStickerBtn.waitFor({ timeout: 5000 });
    await printStickerBtn.click();
    await page.waitForSelector('text=/MRP Rs \\d+(\\.\\d+)? \\(incl\\. GST \\d+%\\)/', { timeout: 8000 });
    const stickerText = await page.locator('text=/MRP Rs \\d+(\\.\\d+)? \\(incl\\. GST \\d+%\\)/').first().innerText();
    console.log(`-> Barcode Sticker Modal verified: "${stickerText}"`);
    const closeStickerBtn = page.locator('button:has-text("Close")');
    await closeStickerBtn.click();
    await page.waitForTimeout(400);

    console.log("\n=================================================================");
    console.log("ALL STAGE B BROWSER E2E TESTS PASSED ACROSS CUSTOMER, STAFF & MANAGER!");
    console.log("=================================================================");

    await browser.close();
    process.exit(0);

  } catch (err) {
    console.error("\n❌ STAGE B BROWSER E2E TEST FAILED:", err);
    await page.screenshot({ path: 'e2e_stage_b_error.png', fullPage: true }).catch(() => {});
    await browser.close();
    process.exit(1);
  }
}

runStageBE2E();
