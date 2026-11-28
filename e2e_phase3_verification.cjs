const { chromium } = require('d:/smartscan-2026/frontend/node_modules/playwright');

async function runE2E() {
  console.log("=================================================================");
  console.log("SMARTSCAN 2026 — PHASE 3 BROWSER END-TO-END VERIFICATION");
  console.log("=================================================================");

  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, // Mobile portrait PWA view
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 SmartScanApp'
  });

  const page = await context.newPage();

  try {
    // -------------------------------------------------------------
    // Step 1: Customer Login
    // -------------------------------------------------------------
    console.log("\n[Step 1] Navigating to http://127.0.0.1:5173 & Customer Login...");
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' });
    
    // Clear storage for clean session
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' });

    // Fill login
    const emailInput = page.locator('input[type="email"]');
    if (await emailInput.isVisible()) {
      await emailInput.fill('demo@smartscan.app');
      await page.locator('input[type="password"]').fill('SmartScanDemo2026!');
      await page.locator('button[type="submit"]').click();
      console.log("-> Submitted login credentials");
    }

    // Wait for HomeScreen
    await page.waitForSelector('text=Our Stores', { timeout: 10000 });
    console.log("-> Landed on HomeScreen successfully");

    // -------------------------------------------------------------
    // Step 2: Verify Initial Count Line & Pinned Stores
    // -------------------------------------------------------------
    console.log("\n[Step 2] Verifying '103 stores - Dehradun' count line & pinned demo stores...");
    const countLine = page.locator('text=/103 stores - Dehradun/');
    await countLine.waitFor({ timeout: 5000 });
    const countText = await countLine.innerText();
    console.log(`-> Count line verified: "${countText}"`);

    // Verify Demo stores pinned first
    await page.waitForSelector('text=FreshMart', { timeout: 10000 });
    const storeCards = page.locator('div.cursor-pointer span[title]');
    await storeCards.first().waitFor({ timeout: 5000 });
    const firstThree = [];
    const count = await storeCards.count();
    for (let i = 0; i < Math.min(count, 3); i++) {
      firstThree.push(await storeCards.nth(i).innerText());
    }
    console.log(`-> First 3 pinned stores: ${JSON.stringify(firstThree)}`);
    if (!firstThree[0].includes('FreshMart') || !firstThree[1].includes('StyleHub') || !firstThree[2].includes('DailyNeeds')) {
      throw new Error(`Demo stores not pinned first! Found: ${JSON.stringify(firstThree)}`);
    }
    console.log("-> Verified FreshMart, StyleHub, DailyNeeds pinned first!");

    // -------------------------------------------------------------
    // Step 3: Test Area Chip Filter (Rajpur Road)
    // -------------------------------------------------------------
    console.log("\n[Step 3] Testing 'Rajpur Road' area chip...");
    const rajpurChip = page.locator('button:has-text("Rajpur Road")').first();
    await rajpurChip.waitFor({ timeout: 5000 });
    const chipText = await rajpurChip.innerText();
    console.log(`-> Found chip: "${chipText}"`);
    if (!chipText.includes('10')) {
      throw new Error(`Expected Rajpur Road chip to show count 10, got "${chipText}"`);
    }

    await rajpurChip.click();
    await page.waitForTimeout(500);

    const filteredRajpurCount = page.locator('text=/10 stores - Dehradun/');
    await filteredRajpurCount.waitFor({ timeout: 5000 });
    console.log("-> Count line updated to: '10 stores - Dehradun'");

    // Toggle back or click All
    const allChip = page.locator('button:has-text("All")').first();
    await allChip.click();
    await page.waitForTimeout(500);
    await countLine.waitFor({ timeout: 5000 });
    console.log("-> Reset back to All (103 stores)");

    // -------------------------------------------------------------
    // Step 4: Test Search Box Filter ("Clement")
    // -------------------------------------------------------------
    console.log("\n[Step 4] Testing Search box filter for 'Clement'...");
    const searchInput = page.locator('input[placeholder*="Search stores"]');
    await searchInput.fill('Clement');
    await page.waitForTimeout(500);

    const clementCount = page.locator('text=/8 stores - Dehradun/');
    await clementCount.waitFor({ timeout: 5000 });
    console.log("-> Search 'Clement' filtered count line: '8 stores - Dehradun'");

    // Verify visible store cards are Clement Town
    const visibleCards = page.locator('text=/Clement Town/');
    const clementStoreCardsCount = await visibleCards.count();
    console.log(`-> Found ${clementStoreCardsCount} store cards matching 'Clement Town'`);
    if (clementStoreCardsCount < 1) {
      throw new Error("No Clement Town store cards displayed!");
    }

    // -------------------------------------------------------------
    // Step 5: Network Store End-to-End Checkout
    // -------------------------------------------------------------
    console.log("\n[Step 5] Clicking network store in Clement Town & executing checkout...");
    const clementStore = page.locator('.cursor-pointer:has-text("Clement Town")').first();
    await clementStore.click();

    // If modal appears, confirm switch
    const switchModal = page.locator('text=Switch Store?');
    if (await switchModal.isVisible({ timeout: 1500 }).catch(() => false)) {
      console.log("-> Confirming store switch modal");
      await page.locator('button:has-text("Switch Store")').click();
    }

    // Inside network store screen, click Open Scanner
    await page.waitForSelector('text=Open Scanner', { timeout: 10000 });
    console.log("-> Inside network store screen, opening scanner...");
    await page.locator('text=Open Scanner').click();

    // Inside network store scanner screen
    // Manual barcode entry for 'Britannia Bread 400g'
    const barcodeInput = page.locator('input[placeholder*="8901234567890"]');
    await barcodeInput.waitFor({ timeout: 8000 });
    await barcodeInput.fill('8907000000255');
    await page.locator('button:has-text("Look Up")').click();
    console.log("-> Looked up barcode '8907000000255'");

    // Verify product result card
    await page.waitForSelector('text=Britannia Bread 400g', { timeout: 8000 });
    console.log("-> Product verified in network store: 'Britannia Bread 400g'");

    // Add to cart
    const addToCartBtn = page.locator('button:has-text("Add to Cart")');
    await addToCartBtn.click();
    console.log("-> Added product to cart");

    // Go to cart
    const viewCartBtn = page.locator('text=/View Cart/');
    await viewCartBtn.waitFor({ timeout: 5000 });
    await viewCartBtn.click();
    console.log("-> Navigated to Cart screen");

    // Proceed to Pay
    const proceedBtn = page.locator('button:has-text("Proceed to Pay")');
    await proceedBtn.waitFor({ timeout: 5000 });
    await proceedBtn.click();
    console.log("-> Clicked 'Proceed to Pay' button");

    // Pay with Mock UPI
    const payBtn = page.locator('button:has-text("Pay ₹")');
    await payBtn.waitFor({ timeout: 5000 });
    await payBtn.click();
    console.log("-> Initiated Mock UPI payment");

    // Verify digital receipt bill
    await page.waitForSelector('text=/SS-\\d+/', { timeout: 10000 });
    const billElement = page.locator('text=/SS-\\d+/').first();
    const generatedBill = await billElement.innerText();
    console.log(`-> Checkout complete! Digital receipt verified with bill: "${generatedBill}"`);

    // Clean up test order so network orders stay at baseline 9924
    const billMatch = generatedBill.match(/SS-\d+/);
    if (billMatch) {
      const bno = billMatch[0];
      const { execSync } = require('child_process');
      execSync(`python -c "import sys; sys.path.insert(0, 'backend'); from core.db import get_supabase; sb = get_supabase(); res = sb.table('orders').select('id').eq('bill_no', '${bno}').execute().data; oid = res[0]['id'] if res else None; sb.table('exit_verifications').delete().eq('bill_no', '${bno}').execute() if oid else None; sb.table('order_items').delete().eq('order_id', oid).execute() if oid else None; sb.table('orders').delete().eq('id', oid).execute() if oid else None"`);
      console.log(`-> Cleaned up browser test order ${bno} to keep baseline at 9924 network orders.`);
    }

    console.log("\n=================================================================");
    console.log("ALL BROWSER CLICK-THROUGH STEPS PASSED SUCCESSFULLY!");
    console.log("=================================================================");

    await browser.close();
    process.exit(0);

  } catch (err) {
    console.error("\n❌ BROWSER E2E TEST FAILED:", err);
    await page.screenshot({ path: 'e2e_phase3_error.png', fullPage: true }).catch(() => {});
    await browser.close();
    process.exit(1);
  }
}

runE2E();
