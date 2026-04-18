const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ 
    headless: true
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });
  
  const page = await context.newPage();
  
  // Navigate to X login
  console.log('Navigating to X login...');
  await page.goto('https://x.com/i/flow/login?redirect_after_login=%2Fi%2Fgrok', { 
    waitUntil: 'networkidle',
    timeout: 60000 
  });
  
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/01_login_start.png' });
  console.log('Screenshot saved: 01_login_start.png');
  
  // Fill in email/username
  console.log('Entering email...');
  const emailInput = page.locator('input[autocomplete="username"], input[name="text"], input[type="text"]').first();
  await emailInput.waitFor({ timeout: 10000 });
  await emailInput.fill('Devinbrumbelow5@gmail.com');
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/02_email_filled.png' });
  
  // Click Next button
  console.log('Clicking Next...');
  const nextButton = page.locator('button:has-text("Next"), div[role="button"]:has-text("Next")').first();
  await nextButton.click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/03_after_next.png' });
  
  // Check if we need username or password
  const url = page.url();
  console.log('Current URL:', url);
  
  // Try to find password field
  const passwordInput = page.locator('input[name="password"], input[type="password"], input[autocomplete="current-password"]').first();
  
  if (await passwordInput.count() > 0) {
    console.log('Entering password...');
    await passwordInput.fill('DeViN156021');
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/04_password_filled.png' });
    
    // Click Log in
    const loginButton = page.locator('button:has-text("Log in"), div[role="button"]:has-text("Log in")').first();
    await loginButton.click();
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/05_after_login.png' });
    
    console.log('Login attempted. Checking current state...');
    console.log('URL after login:', page.url());
    
    // Check for 2FA or other challenges
    const content = await page.content();
    if (content.includes('verification') || content.includes('Two-factor') || content.includes('2FA') || content.includes('code')) {
      console.log('⚠️  2FA/Code verification detected. Waiting for manual intervention...');
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/06_2fa_challenge.png', fullPage: true });
      await page.waitForTimeout(30000); // Wait for potential 2FA
    }
    
    // Navigate to Grok
    console.log('Navigating to Grok...');
    await page.goto('https://x.com/i/grok', { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(5000);
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/07_grok_page.png', fullPage: true });
    console.log('Screenshot saved: 07_grok_page.png');
    
    // Check if we're on Grok
    const grokUrl = page.url();
    console.log('Grok page URL:', grokUrl);
    const title = await page.title();
    console.log('Page title:', title);
    
    // Look for chat input
    const chatInput = page.locator('textarea, [contenteditable="true"], [role="textbox"]').first();
    const hasChat = await chatInput.count() > 0;
    console.log('Has chat input:', hasChat);
    
    if (hasChat) {
      console.log('✅ Grok chat interface found!');
      
      // Send message
      const message = `I need help optimizing a crypto scalping strategy in Freqtrade. Here's my current situation:

Strategy: Bollinger Bands mean reversion with RSI confirmation on 5m timeframe
Current parameters after hyperopt:
- buy_rsi: 28 (IntParameter 28-35)
- buy_bb_width: 0.026 (DecimalParameter 0.022-0.029)
- buy_volume_ratio: 0.92 (DecimalParameter 0.82-0.95)
- sell_rsi: 62 (IntParameter 62-70)
- stoploss: -0.044 (tried to constrain to -0.009 to -0.004 but it escaped!)
- minimal_roi: {"0": 0.268, "37": 0.07, "89": 0.018, "114": 0}
- trailing_stop_positive: 0.044

Results (17 days backtest):
- Win rate: 25% (target: >48%)
- Profit factor: 0.21 (target: >1.7)
- PnL: -0.67%
- Total trades: 32 (too few!)
- BTC went 0/6 wins
- Max drawdown: 0.78% (good)

The low-vol filter is: (bb_width < 0.030) AND (atr < atr_mean * 0.85)

Questions:
1. Why is stoploss escaping my constraints (-0.044 vs my -0.009 to -0.004 limit)?
2. Why so few trades (32 in 17 days)?
3. Should I remove the low-vol filter or relax it?
4. What parameter changes would improve win rate and profit factor?

This is for a local-only Freqtrade scalping bot. Thank you!`;
      
      await chatInput.fill(message);
      await page.waitForTimeout(1000);
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/08_message_typed.png' });
      
      // Send message (Enter or find send button)
      await chatInput.press('Enter');
      console.log('Message sent!');
      
      // Wait for response
      await page.waitForTimeout(15000);
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/09_grok_response.png', fullPage: true });
      
      // Wait more for streaming response
      await page.waitForTimeout(30000);
      await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/10_final_response.png', fullPage: true });
      
      // Extract response text
      const responseElements = await page.$$eval('[data-testid*="message"], .message-content, .prose, article, [role="article"]', 
        elms => elms.map(e => e.textContent).filter(t => t && t.trim().length > 50)
      );
      
      console.log('\n=== GROK RESPONSE ===');
      console.log(responseElements.join('\n\n---\n\n'));
      
    } else {
      console.log('❌ Grok chat not found. Page content sample:');
      const content = await page.content();
      console.log(content.substring(0, 2000));
    }
    
  } else {
    console.log('Password field not found. Current page:');
    console.log('URL:', page.url());
    console.log('Title:', await page.title());
    const content = await page.content();
    console.log('Content:', content.substring(0, 1000));
  }
  
  await browser.close();
  console.log('\nBrowser session complete.');
})();
