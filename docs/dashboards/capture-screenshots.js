/**
 * Dashboard Screenshot Capture Script
 * Puppeteer를 사용하여 HTML 대시보드를 PNG 이미지로 캡처합니다.
 *
 * Usage:
 *   npm install puppeteer
 *   node docs/dashboards/capture-screenshots.js
 */

const puppeteer = require('puppeteer');
const path = require('path');

const DASHBOARD_PATH = path.resolve(__dirname, 'data-platform-dashboard.html');
const SCREENSHOT_DIR = path.resolve(__dirname, 'screenshots');

async function captureScreenshots() {
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });
    await page.goto(`file://${DASHBOARD_PATH}`, { waitUntil: 'networkidle0' });

    // Wait for Chart.js to render
    await new Promise(resolve => setTimeout(resolve, 2000));

    // 1. Full dashboard overview (top section)
    await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'dashboard-overview.png'),
        clip: { x: 0, y: 0, width: 1440, height: 1100 },
    });
    console.log('✅ dashboard-overview.png captured');

    // 2. AI + Cost section
    const pageHeight = await page.evaluate(() => document.body.scrollHeight);
    await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'dashboard-ai-cost.png'),
        clip: { x: 0, y: 1100, width: 1440, height: Math.min(900, pageHeight - 1100) },
    });
    console.log('✅ dashboard-ai-cost.png captured');

    // 3. Full page screenshot
    await page.screenshot({
        path: path.join(SCREENSHOT_DIR, 'dashboard-full.png'),
        fullPage: true,
    });
    console.log('✅ dashboard-full.png captured');

    // 4. Individual panels — HPA Scaling
    const hpaPanel = await page.$('#hpaChart');
    if (hpaPanel) {
        const hpaBox = await hpaPanel.boundingBox();
        await page.screenshot({
            path: path.join(SCREENSHOT_DIR, 'dashboard-hpa-scaling.png'),
            clip: {
                x: Math.max(0, hpaBox.x - 20),
                y: Math.max(0, hpaBox.y - 50),
                width: hpaBox.width + 40,
                height: hpaBox.height + 80,
            },
        });
        console.log('✅ dashboard-hpa-scaling.png captured');
    }

    // 5. Individual panels — Cost Optimization
    const costPanel = await page.$('#costChart');
    if (costPanel) {
        const costBox = await costPanel.boundingBox();
        await page.screenshot({
            path: path.join(SCREENSHOT_DIR, 'dashboard-cost-optimization.png'),
            clip: {
                x: Math.max(0, costBox.x - 20),
                y: Math.max(0, costBox.y - 50),
                width: costBox.width + 40,
                height: costBox.height + 80,
            },
        });
        console.log('✅ dashboard-cost-optimization.png captured');
    }

    await browser.close();
    console.log('\n🎉 All screenshots captured in:', SCREENSHOT_DIR);
}

captureScreenshots().catch(console.error);
