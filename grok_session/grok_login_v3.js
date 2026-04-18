const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await context.newPage();
  
  // Step 1: Go to X login
  console.log('Step 1: Loading X login...');
  await page.goto('https://x.com/login', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step01_initial.png' });
  
  // Step 2: Find and fill username field
  console.log('Step 2: Finding username field...');
  await page.waitForSelector('input[name="text"]', { timeout: 10000 });
  await page.fill('input[name="text"]', 'Devinbrumbelow5@gmail.com');
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step02_username.png' });
  console.log('Username entered');
  
  // Step 3: Click Next
  console.log('Step 3: Clicking Next...');
  await page.click('button:has-text("Next")');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step03_after_username.png' });
  
  // Check current state
  const currentUrl = page.url();
  console.log('URL after Next:', currentUrl);
  
  // Step 4: Look for password field OR unusual phone/username confirmation
  console.log('Step 4: Checking for password field...');
  
  // X sometimes asks for phone/username confirmation
  const passwordExists = await page.locator('input[name="password"]').count() > 0;
  const textInputExists = await page.locator('input[name="text"]').count() > 0;
  
  if (passwordExists) {
    console.log('Found password field');
    await page.fill('input[name="password"]', 'DeViN156021');
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step04_password.png' });
    
    // Click Log in
    await page.click('button:has-text("Log in")');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step05_logged_in.png' });
    
    // Check if we're logged in
    const afterLoginUrl = page.url();
    console.log('URL after login:', afterLoginUrl);
    
    if (!afterLoginUrl.includes('login')) {
      console.log('✅ Successfully logged in!');
      
      // Navigate to Grok
      console.log('Navigating to Grok...');
      await page.goto('https://x.com/i/grok', { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(5000);
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step06_grok.png', fullPage: true });
      
      // Find chat input
      const chatInput = page.locator('textarea, [data-testid*="tweetTextarea"], div[contenteditable="true"]').first();
      if (await chatInput.count() > 0) {
        console.log('✅ Grok chat found!');
        
        // Type message
        const message = `I need help with a Freqtrade crypto scalping strategy.

Current results (17 days):
- Win rate: 25%
- Profit factor: 0.21
- PnL: -0.67%
- Trades: 32 (too few)
- BTC: 0/6 wins

Parameters:
- buy_rsi: 28
- buy_bb_width: 0.026
- stoploss: -0.044 (escaping my -0.009 to -0.004 constraint!)
- Low-vol filter: bb_width < 0.030 AND atr < atr_mean * 0.85

Questions:
1. Why is stoploss escaping constraints?
2. Why so few trades?
3. Should I remove the low-vol filter?
4. What parameter changes would help?

Thanks!`;
        
        await chatInput.fill(message);
        await page.waitForTimeout(1000);
        await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step07_message.png' });
        
        // Send
        await page.keyboard.press('Enter');
        console.log('Message sent!');
        
        // Wait for response
        await page.waitForTimeout(20000);
        await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step08_response.png', fullPage: true });
        
        // Get response text
        const grokResponse = await page.$$eval('[data-testid*="cellInnerDiv"] div[lang], article div[lang], .css-146c3p1', 
          divs => divs.map(d => d.textContent).filter(t => t.length > 100)
        );
        
        console.log('\n=== GROK RESPONSE ===');
        console.log(grokResponse.join('\n\n---\n\n'));
        
        // Wait more for full response
        await page.waitForTimeout(20000);
        await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step09_final.png', fullPage: true });
        
      } else {
        console.log('❌ Chat input not found');
      }
    } else {
      console.log('❌ Login may have failed or requires additional verification');
    }
    
  } else if (textInputExists) {
    console.log('X is asking for additional confirmation (phone/username)');
    // This happens when X doesn't recognize the device
    console.log('This would require manual intervention');
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step04_confirmation.png', fullPage: true });
    
    // Try to see what it's asking for
    const labels = await page.locator('label, span, div').all();
    for (const label of labels.slice(0, 10)) {
      const text = await label.textContent().catch(() => '');
      if (text.toLowerCase().includes('phone') || text.toLowerCase().includes('username') || text.toLowerCase().includes('confirm')) {
        console.log('Prompt found:', text);
      }
    }
  } else {
    console.log('Neither password nor confirmation field found');
    console.log('Page content may be blocked or have CAPTCHA');
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/step04_unknown.png', fullPage: true });
  }
  
  await browser.close();
  console.log('Session complete');
})();
