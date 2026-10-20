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
