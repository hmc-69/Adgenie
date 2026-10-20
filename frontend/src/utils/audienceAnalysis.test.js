import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatAudienceArchetype,
  isAudienceAnalysisRun,
  parseAudienceAnalysisHistory,
  prepareAudiencePrediction,
} from './audienceAnalysis.js';

const validRun = (id, createdAt = '2026-10-20T10:00:00Z') => ({
  id,
  campaign_id: 7,
  analysis_type: 'audience_analysis',
  input_snapshot: { product_name: 'Wireless earbuds' },
  result: {
    audience_overview: 'Potential customers for wireless earbuds.',
    segments: [
      {
        name: 'Commuters',
        description: 'People who listen while traveling.',
        relevant_interests: ['Music'],
        needs_pain_points: ['Convenience'],
        motivations: ['Simpler daily routines'],
        recommended_message_angle: 'Show the product in a commute.',
      },
      {
        name: 'Students',
        description: 'Students considering everyday audio products.',
        relevant_interests: ['Study'],
        needs_pain_points: ['Flexible use'],
        motivations: ['Explore product options'],
        recommended_message_angle: 'Use factual product details.',
      },
    ],
    targeting_approaches: [{ platform: 'Instagram', approaches: ['Test relevant interests.'] }],
    messaging_recommendations: ['Use supported product claims.'],
    creative_considerations: ['Keep the product prominent.'],
    assumptions: [],
    limitations: ['No platform data was accessed.'],
    missing_information: [],
    recommendation_label: 'AI-generated recommendations, not verified audience data.',
  },
  provider: 'mock',
  model: null,
  created_at: createdAt,
});

test('accepts the backend audience-analysis run response shape', () => {
  assert.equal(isAudienceAnalysisRun(validRun(4)), true);
});

test('prepares a valid ML prediction and sorts all class scores highest first', () => {
  const prediction = prepareAudiencePrediction({
    predicted_archetype: 'business_utility_seekers',
    model_identifier: 'audience-model-long-id',
    model_status: 'synthetic_experiment_only',
    score_type: 'uncalibrated scores',
    class_scores: {
      convenience_seekers: 0.2,
      value_seekers: 0.1,
      quality_seekers: 0.3,
      style_seekers: 0.4,
      learning_seekers: 0.5,
      business_utility_seekers: 0.9,
      hobby_interest_seekers: 0.6,
      gift_shoppers: 0.7,
      general_interest: 0.8,
    },
  });

  assert.equal(prediction.displayName, 'Business Utility Seekers');
  assert.equal(prediction.modelIdentifier, 'audience-model-long-id');
  assert.equal(prediction.hasCompleteScores, true);
  assert.equal(prediction.scoreRows.length, 9);
  assert.deepEqual(prediction.scoreRows.map(({ value }) => value), [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]);
  assert.equal(formatAudienceArchetype('hobby_interest_seekers'), 'Hobby Interest Seekers');
});

test('handles missing prediction and incomplete or invalid score maps', () => {
  assert.equal(prepareAudiencePrediction(undefined), null);
  assert.equal(prepareAudiencePrediction({ predicted_archetype: 'general_interest' }), null);

  const withoutScores = prepareAudiencePrediction({
    predicted_archetype: 'general_interest',
    model_identifier: 'synthetic-model',
  });
  assert.equal(withoutScores.scoreRows.length, 0);
  assert.equal(withoutScores.hasCompleteScores, false);

  const partialScores = prepareAudiencePrediction({
    predicted_archetype: 'general_interest',
    model_identifier: 'synthetic-model',
    class_scores: { general_interest: 0.8, value_seekers: Number.NaN, unknown_class: 0.9 },
  });
  assert.deepEqual(partialScores.scoreRows, [{ label: 'general_interest', value: 0.8 }]);
  assert.equal(partialScores.hasCompleteScores, false);
});

test('older saved analyses without prediction metadata remain valid', () => {
  const oldRun = validRun(5);
  assert.equal(isAudienceAnalysisRun(oldRun), true);
  assert.equal(prepareAudiencePrediction(oldRun.result.model_prediction), null);
});

test('rejects malformed analysis results before rendering', () => {
  const malformed = validRun(4);
  malformed.result.segments = [];
  assert.equal(isAudienceAnalysisRun(malformed), false);
  assert.throws(() => parseAudienceAnalysisHistory({ analyses: [malformed], total: 1 }));
});

test('sorts saved analyses newest first and handles empty history', () => {
  const history = parseAudienceAnalysisHistory({
    analyses: [validRun(1, '2026-10-19T10:00:00Z'), validRun(2, '2026-10-20T10:00:00Z')],
    total: 2,
  });
  assert.deepEqual(history.map((run) => run.id), [2, 1]);
  assert.deepEqual(parseAudienceAnalysisHistory({ analyses: [], total: 0 }), []);
});
