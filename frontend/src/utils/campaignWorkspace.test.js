import test from 'node:test';
import assert from 'node:assert/strict';
import { getCampaignWorkspaceFromHash } from './campaignWorkspace.js';

test('campaign section hashes select the matching visible workspace', () => {
  assert.equal(getCampaignWorkspaceFromHash('#creative-studio'), 'creative');
  assert.equal(getCampaignWorkspaceFromHash('#audience-analysis'), 'audience');
  assert.equal(getCampaignWorkspaceFromHash('#campaign-performance'), 'performance');
  assert.equal(getCampaignWorkspaceFromHash('#unknown'), null);
});
