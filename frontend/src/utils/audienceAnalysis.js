const isText = (value) => typeof value === 'string' && value.trim().length > 0;
const isTextList = (value, { allowEmpty = false } = {}) => (
  Array.isArray(value)
  && (allowEmpty || value.length > 0)
  && value.every((item) => typeof item === 'string')
);

const isAudienceSegment = (segment) => (
  segment
  && isText(segment.name)
  && isText(segment.description)
  && isTextList(segment.relevant_interests)
  && isTextList(segment.needs_pain_points)
  && isTextList(segment.motivations)
  && isText(segment.recommended_message_angle)
);

const isTargetingApproach = (approach) => (
  approach
  && isText(approach.platform)
  && isTextList(approach.approaches)
);

export const AUDIENCE_ARCHETYPES = [
  'convenience_seekers',
  'value_seekers',
  'quality_seekers',
  'style_seekers',
  'learning_seekers',
  'business_utility_seekers',
  'hobby_interest_seekers',
  'gift_shoppers',
  'general_interest',
];

export const formatAudienceArchetype = (value) => (
  typeof value === 'string'
    ? value.split('_').filter(Boolean).map((word) => `${word[0].toUpperCase()}${word.slice(1)}`).join(' ')
    : ''
);

export const prepareAudiencePrediction = (prediction) => {
  if (
    !prediction
    || typeof prediction !== 'object'
    || Array.isArray(prediction)
    || !AUDIENCE_ARCHETYPES.includes(prediction.predicted_archetype)
    || !isText(prediction.model_identifier)
  ) {
    return null;
  }

  const rawScores = prediction.class_scores;
  const scoreRows = rawScores && typeof rawScores === 'object' && !Array.isArray(rawScores)
    ? AUDIENCE_ARCHETYPES
      .filter((label) => Number.isFinite(rawScores[label]) && rawScores[label] >= 0 && rawScores[label] <= 1)
      .map((label) => ({ label, value: rawScores[label] }))
      .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label))
    : [];

  return {
    predictedArchetype: prediction.predicted_archetype,
    displayName: formatAudienceArchetype(prediction.predicted_archetype),
    modelIdentifier: prediction.model_identifier,
    scoreRows,
    hasCompleteScores: scoreRows.length === AUDIENCE_ARCHETYPES.length,
  };
};

export const isAudienceAnalysisRun = (run) => {
  const result = run?.result;
  return Boolean(
    run
    && Number.isInteger(run.id)
    && Number.isInteger(run.campaign_id)
    && run.analysis_type === 'audience_analysis'
    && run.input_snapshot
    && typeof run.input_snapshot === 'object'
    && !Array.isArray(run.input_snapshot)
    && isText(run.created_at)
    && result
    && isText(result.audience_overview)
    && Array.isArray(result.segments)
    && result.segments.length >= 2
    && result.segments.every(isAudienceSegment)
    && Array.isArray(result.targeting_approaches)
    && result.targeting_approaches.length > 0
    && result.targeting_approaches.every(isTargetingApproach)
    && isTextList(result.messaging_recommendations)
    && isTextList(result.creative_considerations)
    && isTextList(result.assumptions, { allowEmpty: true })
    && isTextList(result.limitations)
    && isTextList(result.missing_information, { allowEmpty: true })
    && (result.recommendation_label === undefined || isText(result.recommendation_label))
    && (run.provider === null || run.provider === undefined || typeof run.provider === 'string')
    && (run.model === null || run.model === undefined || typeof run.model === 'string')
  );
};

export const parseAudienceAnalysisHistory = (payload) => {
  if (
    !payload
    || !Array.isArray(payload.analyses)
    || !Number.isInteger(payload.total)
    || payload.total < payload.analyses.length
    || !payload.analyses.every(isAudienceAnalysisRun)
  ) {
    throw new Error('The audience-analysis history response was incomplete or invalid.');
  }
  return [...payload.analyses].sort((left, right) => {
    const dateDifference = Date.parse(right.created_at) - Date.parse(left.created_at);
    return Number.isNaN(dateDifference) || dateDifference === 0
      ? right.id - left.id
      : dateDifference;
  });
};

export const formatAudienceAnalysisDate = (value) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Date unavailable';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};
