import test from 'node:test';
import assert from 'node:assert/strict';
import { apiClient, setUnauthorizedHandler } from './client.js';

const unauthorizedInterceptor = apiClient.interceptors.response.handlers[0].rejected;

test('401 expiration clears the token and resets in-memory auth state', async () => {
  const originalStorage = globalThis.localStorage;
  const values = new Map([['adgenie_auth_token', 'expired-token']]);
  globalThis.localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
  let resetCalls = 0;
  setUnauthorizedHandler(() => { resetCalls += 1; });
  try {
    const error = { config: { url: '/api/campaigns' }, response: { status: 401 } };
    await assert.rejects(unauthorizedInterceptor(error), (received) => received === error);
    assert.equal(values.has('adgenie_auth_token'), false);
    assert.equal(resetCalls, 1);
  } finally {
    setUnauthorizedHandler(null);
    globalThis.localStorage = originalStorage;
  }
});

test('login 401 does not clear an existing session or invoke the reset handler', async () => {
  const originalStorage = globalThis.localStorage;
  const values = new Map([['adgenie_auth_token', 'current-token']]);
  globalThis.localStorage = { removeItem: (key) => values.delete(key) };
  let resetCalls = 0;
  setUnauthorizedHandler(() => { resetCalls += 1; });
  try {
    const error = { config: { url: '/api/auth/login' }, response: { status: 401 } };
    await assert.rejects(unauthorizedInterceptor(error));
    assert.equal(values.get('adgenie_auth_token'), 'current-token');
    assert.equal(resetCalls, 0);
  } finally {
    setUnauthorizedHandler(null);
    globalThis.localStorage = originalStorage;
  }
});
