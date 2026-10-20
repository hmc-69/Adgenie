import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createVideoPlaybackUrl,
  getRenderedVideoPath,
  isTerminalVideoStatus,
} from './videoPlayback.js';

test('creates a browser playback URL from the authenticated MP4 response blob', () => {
  const originalCreateObjectURL = URL.createObjectURL;
  const blob = new Blob([new Uint8Array([0, 0, 0, 24])], { type: 'video/mp4' });
  URL.createObjectURL = (receivedBlob) => {
    assert.equal(receivedBlob, blob);
    assert.equal(receivedBlob.type, 'video/mp4');
    return 'blob:adgenie-video';
  };

  try {
    assert.equal(createVideoPlaybackUrl(blob), 'blob:adgenie-video');
  } finally {
    URL.createObjectURL = originalCreateObjectURL;
  }
});

test('uses the backend playback URL and retains the authenticated route fallback', () => {
  assert.equal(
    getRenderedVideoPath(7, 12, '/api/creative/campaign/7/video/12'),
    '/api/creative/campaign/7/video/12',
  );
  assert.equal(
    getRenderedVideoPath(7, 12, undefined),
    '/api/creative/campaign/7/video/12',
  );
});

test('stops render polling for completed and failed backend statuses', () => {
  assert.equal(isTerminalVideoStatus('completed'), true);
  assert.equal(isTerminalVideoStatus('failed'), true);
  assert.equal(isTerminalVideoStatus('pending'), false);
  assert.equal(isTerminalVideoStatus('running'), false);
});
