import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { resolve } from 'node:path';
import { cwd } from 'node:process';

test('campaign performance section renders the manual entry form and historical results heading', async () => {
  const vite = await createServer({
    configFile: resolve(cwd(), 'vite.config.js'),
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'silent',
  });
  try {
    const { CampaignPerformance } = await vite.ssrLoadModule('/src/components/CampaignPerformance.jsx');
    const html = renderToStaticMarkup(React.createElement(CampaignPerformance, { campaignId: 12 }));
    assert.match(html, /Campaign Performance/);
    assert.match(html, /Record daily results/);
    assert.match(html, /Actual spend \(USD\)/);
    assert.match(html, /Revenue \(USD, optional\)/);
    assert.match(html, /Based on manually entered campaign results/);
  } finally {
    await vite.close();
  }
});
