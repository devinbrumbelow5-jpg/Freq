const { chromium } = require('playwright');

(async () => {
  console.log('Launching browser...');
  const browser = await chromium.launch({ 
    headless: true
  });
  
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });
  
  const page = await context.newPage();
  
  console.log('Navigating to grok.x.ai...');
  await page.goto('https://grok.x.ai', { waitUntil: 'networkidle' });
  
  // Wait a bit for any redirects or loading
  await page.waitForTimeout(3000);
  
  // Take screenshot to see current state
  await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/01_initial_page.png', fullPage: true });
  console.log('Screenshot saved: 01_initial_page.png');
  
  // Check if we're on login page or chat page
  const url = page.url();
  console.log('Current URL:', url);
  
  // Check for login elements
  const hasEmailInput = await page.locator('input[type="email"], input[name="email"], input[name="text"]').count() > 0;
  const hasPasswordInput = await page.locator('input[type="password"]').count() > 0;
  const hasChatInput = await page.locator('textarea, [contenteditable="true"], input[placeholder*="message"], input[placeholder*="ask"]').count() > 0;
  
  console.log('Page analysis:');
  console.log('  - Has email input:', hasEmailInput);
  console.log('  - Has password input:', hasPasswordInput);
  console.log('  - Has chat input:', hasChatInput);
  
  if (hasEmailInput || hasPasswordInput) {
    console.log('\n⚠️  LOGIN REQUIRED');
    console.log('Grok requires authentication. The page shows a login form.');
    console.log('Please provide X/Twitter credentials to proceed.');
    
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/02_login_page.png', fullPage: true });
    console.log('Login page screenshot saved: 02_login_page.png');
    
    // Keep browser open for manual login
    console.log('\nBrowser will stay open for 60 seconds. You can manually login if you have a display.');
    await page.waitForTimeout(60000);
  } else if (hasChatInput) {
    console.log('\n✅ Chat interface detected');
    
    // Find and click chat input
    const chatInput = page.locator('textarea, [contenteditable="true"]').first();
    await chatInput.click();
    
    // Type message
    const message = `I'm working on a crypto scalping strategy in Freqtrade. The strategy uses Bollinger Bands mean reversion with RSI confirmation. Current parameters after hyperopt:
- buy_rsi: 28
- buy_bb_width: 0.026
- stoploss: -0.044
- Result: 25% win rate, 0.21 profit factor, -0.67% PnL over 17 days

The low-volatility filter (bb_width < 0.030 AND atr < atr_mean * 0.85) is causing only 32 trades in 17 days. BTC went 0/6.

What changes would you recommend to improve this scalping strategy?`;
    
    await chatInput.fill(message);
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/03_message_typed.png' });
    
    // Submit message (look for send button or press Enter)
    const sendButton = await page.locator('button[type="submit"], button:has-text("Send"), [aria-label*="send"]').first();
    if (await sendButton.count() > 0) {
      await sendButton.click();
    } else {
      await chatInput.press('Enter');
    }
    
    console.log('Message sent. Waiting for response...');
    await page.waitForTimeout(10000);
    
    // Take screenshot of response
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/04_grok_response.png', fullPage: true });
    console.log('Response screenshot saved: 04_grok_response.png');
    
    // Extract conversation text
    const messages = await page.$$eval('[data-testid*="message"], .message, .chat-message, [role="article"]', msgs => 
      msgs.map(m => m.textContent).filter(t => t && t.trim())
    );
    
    console.log('\n=== GROK CONVERSATION ===');
    messages.forEach((msg, i) => {
      console.log(`\n[Message ${i + 1}]:`);
      console.log(msg.substring(0, 500));
    });
    
    // Wait longer for streaming response
    await page.waitForTimeout(30000);
    await page.screenshot({ path: '/root/.openclaw/workspace/grok_session/05_final_response.png', fullPage: true });
    
    // Extract final response text
    const finalMessages = await page.$$eval('[data-testid*="message"], .message, .chat-message, [role="article"], .prose', msgs => 
      msgs.map(m => m.textContent).filter(t => t && t.trim())
    );
    
    console.log('\n=== FINAL GROK RESPONSE ===');
    console.log(finalMessages.join('\n\n---\n\n'));
    
  } else {
    console.log('\n❓ Unknown page state');
    console.log('Page title:', await page.title());
    console.log('Page HTML sample:', await page.content().then(c => c.substring(0, 1000)));
  }
  
  await browser.close();
  console.log('\nBrowser session complete.');
})();
