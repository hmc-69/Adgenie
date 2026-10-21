import test from 'node:test';
import assert from 'node:assert/strict';
import { apiClient } from './client.js';
import { creativeService } from './creativeService.js';

test('image brief generation uses the backend POST route and campaign payload', async () => {
  const originalPost = apiClient.post;
  const originalGet = apiClient.get;
  const calls = [];
  apiClient.post = async (...args) => {
    calls.push(['POST', ...args]);
    return { data: { generated_content: {} } };
  };
  apiClient.get = async (...args) => {
    calls.push(['GET', ...args]);
    return { data: { generated_content: {} } };
  };

  try {
    await creativeService.generateImageBrief(8);
    assert.deepEqual(calls, [[
      'POST',
      '/api/creative/image-brief',
      { campaign_id: 8 },
      { timeout: 120_000 },
    ]]);
  } finally {
    apiClient.post = originalPost;
    apiClient.get = originalGet;
  }
});

test('video script generation uses its backend POST route', async () => {
  const originalPost = apiClient.post;
  const originalGet = apiClient.get;
  const calls = [];
  apiClient.post = async (...args) => {
    calls.push(['POST', ...args]);
    return { data: { generated_content: {} } };
  };
  apiClient.get = async (...args) => {
    calls.push(['GET', ...args]);
    return { data: { generated_content: {} } };
  };

  try {
    await creativeService.generateVideoScript(9);
    assert.deepEqual(calls, [[
      'POST',
      '/api/creative/video-script',
      { campaign_id: 9 },
      { timeout: 120_000 },
    ]]);
  } finally {
    apiClient.post = originalPost;
    apiClient.get = originalGet;
  }
});
