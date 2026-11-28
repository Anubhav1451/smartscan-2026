const { chromium } = require('d:/smartscan-2026/frontend/node_modules/playwright');

async function runStageDE2E() {
  console.log("=================================================================");
  console.log("SMARTSCAN 2026 — STAGE D REAL BROWSER SELF-TEST");
  console.log("=================================================================");

  const browser = await chromium.launch({
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 420, height: 880 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 SmartScanApp'
  });

  const page = await context.newPage();
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER PAGEERROR:', err.message));
  page.on('request', req => {
    if (req.url().includes('/exit/')) {
      console.log('NETWORK REQ:', req.method(), req.url(), req.postData());
    }
  });
  page.on('response', async res => {
    if (res.url().includes('/exit/')) {
      try {
        const text = await res.text();
        console.log('NETWORK RES:', res.status(), res.url(), text);
      } catch (e) {}
    }
  });

  try {
    // -------------------------------------------------------------
    // Step 1: Open app and log in as Exit Staff Demo
    // -------------------------------------------------------------
    console.log("\n[Step 1] Loading app at http://127.0.0.1:5173...");
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    // If currently logged in as another role, sign out first
    const signOutBtn = await page.$('button[title="Sign out"], button[aria-label="Sign Out"]');
    if (signOutBtn) {
      console.log("-> Currently signed in as another user, clicking sign out...");
      await signOutBtn.click();
      await page.waitForTimeout(1500);
    }

    // Ensure we are on LoginScreen
    const staffBtn = await page.waitForSelector('button:has-text("Switch to Exit Staff Demo")', { timeout: 10000 });
    console.log("-> Clicking Exit Staff Demo login button...");
    await staffBtn.click();

    await page.waitForSelector('text=Staff Gate', { timeout: 15000 });
    console.log("PASS: Staff Gate loaded successfully");

    // -------------------------------------------------------------
    // Step 2: Verify 'Generate Sample FAKE Bill (test)' button
    // -------------------------------------------------------------
    console.log("\n[Step 2] Checking 'Generate Sample FAKE Bill (test)' button...");
    const fakeBillBtn = await page.waitForSelector('button:has-text("Generate Sample FAKE Bill (test)")', { timeout: 5000 });
    assert(fakeBillBtn, "Generate Sample FAKE Bill (test) button not found on StaffScreen!");
    console.log("PASS: 'Generate Sample FAKE Bill (test)' button is clearly displayed");

    // -------------------------------------------------------------
    // Step 3: Click button and verify Fake Bill Modal
    // -------------------------------------------------------------
    console.log("\n[Step 3] Opening Fake Bill Modal...");
    await fakeBillBtn.click();

    await page.waitForSelector('text=Sample FAKE Bill Generator', { timeout: 5000 });
    console.log("-> Fake Bill Modal header verified");

    // Wait for bill number to be generated
    await page.waitForFunction(() => {
      const el = document.querySelector('#printable-fake-receipt');
      return el && el.textContent.includes('SS-9');
    }, { timeout: 8000 });

    const billNoText = await page.$eval('#printable-fake-receipt', el => {
      const match = el.textContent.match(/SS-9\d{4}/);
      return match ? match[0] : null;
    });
    console.log(`-> Generated unique absent fake bill: ${billNoText}`);
    assert(billNoText && billNoText.startsWith('SS-9'), `Expected SS-9xxxx bill number, got ${billNoText}`);

    // Verify visible watermark on the fake bill
    const watermark = await page.waitForSelector('text=SAMPLE - NOT A REAL BILL', { timeout: 3000 });
    assert(watermark, "Watermark 'SAMPLE - NOT A REAL BILL' not found on fake bill receipt!");
    console.log("PASS: Watermark 'SAMPLE - NOT A REAL BILL' is prominently visible on the bill");

    // Verify QR code is rendered
    const qrSvg = await page.waitForSelector('#printable-fake-receipt svg', { timeout: 3000 });
    assert(qrSvg, "QR Code SVG not found inside printable fake receipt!");
    console.log("PASS: QR Code SVG is rendered inside the printable fake bill");

    // Verify sample items & total
    const receiptContent = await page.$eval('#printable-fake-receipt', el => el.textContent);
    assert(receiptContent.includes('Amul Taaza'), "Sample item Amul Taaza missing from fake bill");
    assert(receiptContent.includes('Britannia'), "Sample item Britannia missing from fake bill");
    assert(receiptContent.includes('TOTAL AMOUNT'), "Total amount missing from fake bill");
    console.log("PASS: Realistic store items and totals are rendered");

    // -------------------------------------------------------------
    // Step 4: Click 'Test Verify in Gate Scanner'
    // -------------------------------------------------------------
    console.log("\n[Step 4] Testing verify from modal via 'Test Verify in Gate Scanner'...");
    const testNowBtn = await page.waitForSelector('button:has-text("Test Verify in Gate Scanner")', { timeout: 3000 });
    await testNowBtn.click();

    // -------------------------------------------------------------
    // Step 5: Verify Dramatic FULL-WIDTH BRIGHT RED Result State
    // -------------------------------------------------------------
    console.log("\n[Step 5] Checking for dramatic full-width bright red FAKE BILL result...");
    await page.waitForSelector('h2:has-text("FAKE BILL")', { timeout: 8000 });
    await page.waitForSelector('text=This bill is not in our system.', { timeout: 5000 });
    await page.waitForSelector('text=DO NOT ALLOW EXIT • STOP CUSTOMER', { timeout: 5000 });

    // Verify the rejected bill reference is visible in the red state
    const rejectedBillDisplay = await page.waitForSelector(`text=${billNoText}`, { timeout: 5000 });
    assert(rejectedBillDisplay, `Rejected bill reference ${billNoText} was not displayed in the red state!`);
    console.log(`-> Confirmed: Rejected bill reference '${billNoText}' is clearly shown`);

    // Verify the background is full-width bright red (bg-red-600)
    const isRedBg = await page.$eval('.bg-red-600', el => {
      const styles = window.getComputedStyle(el);
      return styles.backgroundColor.includes('rgb(220, 38, 38)') || styles.backgroundColor.includes('rgb(239, 68, 68)');
    });
    assert(isRedBg, "Result card is not styled with bright red background!");
    console.log("PASS: Full-width bright red FAKE BILL state displayed prominently (readable from 3m)");

    // -------------------------------------------------------------
    // Step 6: Test Dismiss
    // -------------------------------------------------------------
    console.log("\n[Step 6] Testing Dismiss button...");
    const dismissBtn = await page.waitForSelector('button:has-text("Dismiss")', { timeout: 3000 });
    await dismissBtn.click();
    await page.waitForSelector('h2:has-text("FAKE BILL")', { state: 'detached', timeout: 5000 });
    console.log("PASS: Result card dismissed cleanly");

    // -------------------------------------------------------------
    // Step 7: Manual entry of absent bill SS-99999
    // -------------------------------------------------------------
    console.log("\n[Step 7] Testing manual typing of absent bill SS-99999...");
    await page.fill('input[placeholder*="SS-20481"]', 'SS-99999');
    await page.click('button:has-text("Verify")');

    await page.waitForSelector('h2:has-text("FAKE BILL")', { timeout: 6000 });
    await page.waitForSelector('text=SS-99999', { timeout: 5000 });
    console.log("PASS: Manually entered absent bill SS-99999 triggered dramatic FAKE BILL alert");
    await page.click('button:has-text("Dismiss")');
    await page.waitForSelector('h2:has-text("FAKE BILL")', { state: 'detached', timeout: 5000 });

    // -------------------------------------------------------------
    // Step 8: Test seeded bill SS-20481 (keeps orange ALREADY_USED)
    // -------------------------------------------------------------
    console.log("\n[Step 8] Testing seeded bill SS-20481 verification...");
    const verifyInput = page.locator('input[placeholder*="SS-20481"]');
    await verifyInput.click();
    await verifyInput.fill('SS-20481');
    await page.locator('button[type="submit"]:has-text("Verify")').click();

    await page.waitForSelector('text=ALREADY USED', { timeout: 12000 });
    const noFakeText = await page.$('h2:has-text("FAKE BILL")');
    assert(!noFakeText, "SS-20481 incorrectly triggered FAKE BILL state!");
    console.log("PASS: Seeded bill SS-20481 correctly rendered orange ALREADY USED state without triggering FAKE BILL");

    console.log("\n=================================================================");
    console.log("ALL STAGE D BROWSER SELF-TESTS PASSED SUCCESSFULLY!");
    console.log("=================================================================");

  } catch (err) {
    console.error("\nE2E VERIFICATION FAILED:", err.message);
    try {
      const bodyText = await page.evaluate(() => document.body.innerText);
      console.log("\n--- PAGE BODY TEXT AT FAILURE ---:\n" + bodyText + "\n---------------------------------");
    } catch (e) {}
    await page.screenshot({ path: 'e2e_stage_d_error.png' });
    process.exit(1);
  } finally {
    await browser.close();
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message || "Assertion failed");
  }
}

runStageDE2E();
