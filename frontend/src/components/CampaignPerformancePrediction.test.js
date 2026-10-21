import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
import { resolve } from 'node:path';
import { cwd } from 'node:process';

const predictionResponse = {
  campaign_id: 8,
  prediction_type: 'synthetic_experiment_only',
  model_version: 'campaign-performance-test-v1',
  predictions: { ctr_percent: 2.345, conversion_rate_percent: 3.456 },
  units: { ctr_percent: '%', conversion_rate_percent: '%' },
  evaluation: {
    dataset_type: 'synthetic',
    ctr: {
      selected_model: 'linear_regression',
      test_mae: 0.42,
      test_rmse: 0.55,
      test_r2: 0.61,
      baseline_model: 'dummy_mean',
      baseline_test_mae: 0.7,
      baseline_test_rmse: 0.82,
      baseline_test_r2: -0.01,
      meaningful_improvement_over_baseline: true,
    },
    conversion_rate: null,
  },
  limitations: ['Synthetic experiment only.'],
  output_bound_strategy: 'Clip output to [0, 100].',
};

test('prediction section renders its warning and separates estimates from recorded analytics', async () => {
  const vite = await createServer({
    configFile: resolve(cwd(), 'vite.config.js'),
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'silent',
  });
  try {
    const { CampaignPerformancePrediction, CampaignPredictionResults } = await vite.ssrLoadModule('/src/components/CampaignPerformancePrediction.jsx');
    const emptyHtml = renderToStaticMarkup(React.createElement(CampaignPerformancePrediction, { campaignId: 8 }));
    assert.match(emptyHtml, /Campaign Performance Prediction/);
    assert.match(emptyHtml, /synthetic data only/i);
    assert.match(emptyHtml, /No prediction has been requested/);
    assert.match(emptyHtml, /Predict Performance/);
    assert.doesNotMatch(emptyHtml, /Recorded performance/);

    const resultHtml = renderToStaticMarkup(React.createElement(CampaignPredictionResults, { prediction: predictionResponse }));
    assert.match(resultHtml, /Predicted CTR/);
    assert.match(resultHtml, /2\.35%/);
    assert.match(resultHtml, /Predicted conversion rate/);
    assert.match(resultHtml, /3\.46%/);
    assert.match(resultHtml, /campaign-performance-test-v1/);
    assert.match(resultHtml, /Dummy baseline MAE: 0\.700/);
    assert.match(resultHtml, /Evaluation metrics unavailable/);
    assert.match(resultHtml, /not validated for real-world accuracy/i);
  } finally {
    await vite.close();
  }
});
