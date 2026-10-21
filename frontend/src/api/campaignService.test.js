import test from 'node:test';
import assert from 'node:assert/strict';
import { apiClient } from './client.js';
import { campaignService, getApiErrorMessage } from './campaignService.js';

test('audience analysis POST uses the registered route and a longer request timeout', async () => {
  const originalPost = apiClient.post;
  let call;
  apiClient.post = async (...args) => {
    call = args;
    return { data: { id: 19 } };
  };

  try {
    const result = await campaignService.createAudienceAnalysis(8);
    assert.deepEqual(result, { id: 19 });
    assert.equal(call[0], '/api/campaigns/8/audience-analysis');
    assert.equal(call[1], undefined);
    assert.equal(call[2].timeout, 120_000);
  } finally {
    apiClient.post = originalPost;
  }
});

test('canceled and timed out requests are not reported as API connectivity failures', () => {
  assert.match(
    getApiErrorMessage({ code: 'ERR_CANCELED', name: 'CanceledError' }),
    /request was canceled/i,
  );
  assert.match(
    getApiErrorMessage({ code: 'ECONNABORTED', message: 'timeout of 10000ms exceeded', isAxiosError: true }),
    /too long to finish/i,
  );
});

test('non-Axios exceptions use the supplied fallback instead of a network error', () => {
  assert.equal(getApiErrorMessage(new Error('response validation failed'), 'Audience response was invalid.'), 'Audience response was invalid.');
});

test('campaign performance API uses the registered methods, paths, params, and payload', async () => {
  const originalPost = apiClient.post;
  const originalGet = apiClient.get;
  const calls = [];
  apiClient.post = async (...args) => {
    calls.push(['POST', ...args]);
    return { data: { id: 3, date: '2026-10-20' } };
  };
  apiClient.get = async (...args) => {
    calls.push(['GET', ...args]);
    return { data: args[0].endsWith('/analytics') ? { impressions: 100 } : { records: [], total: 0 } };
  };

  const payload = { date: '2026-10-20', impressions: 100, clicks: 10, conversions: 2, spend: 5, revenue: null };
  const dateRange = { start_date: '2026-10-01', end_date: '2026-10-31' };
  try {
    assert.deepEqual(await campaignService.recordCampaignPerformance(8, payload), { id: 3, date: '2026-10-20' });
    assert.deepEqual(await campaignService.getCampaignPerformance(8, dateRange), { records: [], total: 0 });
    assert.deepEqual(await campaignService.getCampaignPerformanceAnalytics(8, dateRange), { impressions: 100 });
    assert.deepEqual(calls, [
      ['POST', '/api/campaigns/8/performance', payload],
      ['GET', '/api/campaigns/8/performance', { params: dateRange }],
      ['GET', '/api/campaigns/8/performance/analytics', { params: dateRange }],
    ]);
  } finally {
    apiClient.post = originalPost;
    apiClient.get = originalGet;
  }
});

test('performance API validation and duplicate errors are surfaced from the server', () => {
  assert.equal(
    getApiErrorMessage({ response: { status: 409, data: { detail: 'A performance record already exists.' } } }),
    'A performance record already exists.',
  );
  assert.equal(
    getApiErrorMessage({ response: { status: 422, data: { detail: [{ msg: 'Clicks cannot exceed impressions.' }] } } }),
    'Clicks cannot exceed impressions.',
  );
});

test('campaign performance prediction uses its dedicated POST endpoint without outcome payload', async () => {
  const originalPost = apiClient.post;
  let call;
  apiClient.post = async (...args) => {
    call = args;
    return { data: { campaign_id: 8, prediction_type: 'synthetic_experiment_only' } };
  };
  try {
    const result = await campaignService.predictCampaignPerformance(8);
    assert.deepEqual(result, { campaign_id: 8, prediction_type: 'synthetic_experiment_only' });
    assert.deepEqual(call, ['/api/campaigns/8/performance/predict']);
  } finally {
    apiClient.post = originalPost;
  }
});
