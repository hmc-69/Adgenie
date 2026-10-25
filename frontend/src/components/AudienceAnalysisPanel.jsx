import { useEffect, useRef, useState } from 'react';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import {
  formatAudienceAnalysisDate,
  formatAudienceArchetype,
  isAudienceAnalysisRun,
  parseAudienceAnalysisHistory,
  prepareAudiencePrediction,
} from '../utils/audienceAnalysis';

const ANALYSIS_NOTICE = 'These are AI-generated recommendations based on campaign context, not verified audience data.';

const RecommendationList = ({ items, emptyMessage }) => (
  Array.isArray(items) && items.length > 0
    ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
    : <p className="audience-empty-copy">{emptyMessage}</p>
);

const AudienceAnalysisResultView = ({ run, isLatest }) => {
  const result = run.result;
  const prediction = prepareAudiencePrediction(result.model_prediction);

  return (
    <div className="audience-result" aria-live="polite">
      <div className="audience-result-heading">
        <div>
          <p className="page-kicker">{isLatest ? 'Latest recommendations' : 'Previous recommendations'}</p>
          <p className="audience-result-date">Saved {formatAudienceAnalysisDate(run.created_at)}</p>
        </div>
        {isLatest && <span className="audience-latest-badge">Latest</span>}
      </div>

      {prediction && (
        <section className="audience-ml-prediction" aria-labelledby="audience-ml-prediction-title">
          <div className="audience-ml-heading">
            <div>
              <p className="page-kicker">Experimental classifier</p>
              <h3 id="audience-ml-prediction-title">ML-Predicted Audience Archetype</h3>
            </div>
            <span className="audience-ml-label">{prediction.displayName}</span>
          </div>

          {prediction.scoreRows.length > 0 ? (
            <ol className="audience-ml-score-list" aria-label="Archetype scores, highest first">
              {prediction.scoreRows.map(({ label, value }) => (
                <li className="audience-ml-score-row" key={label}>
                  <span className="audience-ml-score-label">{formatAudienceArchetype(label)}</span>
                  <progress
                    className="audience-ml-score-bar"
                    value={value}
                    max="1"
                    aria-label={`${formatAudienceArchetype(label)} score`}
                    aria-valuetext={value.toFixed(2)}
                  />
                  <span className="audience-ml-score-value">{value.toFixed(2)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="audience-ml-scores-unavailable">Classifier scores are unavailable for this saved result.</p>
          )}

          {!prediction.hasCompleteScores && prediction.scoreRows.length > 0 && (
            <p className="audience-ml-scores-unavailable">Some classifier scores were missing or invalid.</p>
          )}
          <details className="audience-ml-model-details">
            <summary>Model identifier</summary>
            <code title={prediction.modelIdentifier}>{prediction.modelIdentifier}</code>
          </details>
          <p className="audience-ml-note">
            Experimental ML prediction trained on synthetic data. Scores are uncalibrated and should not be interpreted as verified probabilities or real audience facts.
          </p>
        </section>
      )}

      {!prediction && (
        <section className="audience-ml-prediction" aria-label="ML audience prediction">
          <p className="page-kicker">Experimental classifier</p>
          <h3>ML prediction not available for this saved analysis</h3>
          <p className="audience-ml-scores-unavailable">
            The local classifier could not return a prediction for this saved analysis.
          </p>
        </section>
      )}

      <article className="audience-overview-card">
        <span className="meta-label">Audience overview</span>
        <p>{result.audience_overview}</p>
      </article>

      <section className="audience-result-section" aria-labelledby="audience-segments-title">
        <div className="audience-subsection-heading">
          <h3 id="audience-segments-title">Potential audience segments</h3>
          <span>Recommendations</span>
        </div>
        {Array.isArray(result.segments) && result.segments.length > 0 ? (
          <div className="audience-segment-grid">
            {result.segments.map((segment, index) => (
              <article className="audience-segment-card" key={`${segment.name}-${index}`}>
                <h4>{segment.name}</h4>
                <p className="audience-segment-description">{segment.description}</p>
                <div className="audience-detail-block">
                  <span>Relevant interests</span>
                  <RecommendationList items={segment.relevant_interests} emptyMessage="Not specified." />
                </div>
                <div className="audience-detail-block">
                  <span>Needs and pain points</span>
                  <RecommendationList items={segment.needs_pain_points} emptyMessage="Not specified." />
                </div>
                <div className="audience-detail-block">
                  <span>Motivations</span>
                  <RecommendationList items={segment.motivations} emptyMessage="Not specified." />
                </div>
                <div className="audience-message-angle">
                  <span>Recommended message angle</span>
                  <p>{segment.recommended_message_angle}</p>
                </div>
              </article>
            ))}
          </div>
        ) : <p className="audience-empty-copy">No audience segments were returned for this analysis.</p>}
      </section>

      <div className="audience-guidance-grid">
        <section className="audience-guidance-card">
          <h3>Targeting approaches</h3>
          {Array.isArray(result.targeting_approaches) && result.targeting_approaches.length > 0
            ? result.targeting_approaches.map((approach, index) => (
              <div className="audience-platform-guidance" key={`${approach.platform}-${index}`}>
                <h4>{approach.platform}</h4>
                <RecommendationList items={approach.approaches} emptyMessage="No approaches were specified." />
              </div>
            ))
            : <p className="audience-empty-copy">No targeting approaches were returned.</p>}
        </section>
        <section className="audience-guidance-card">
          <h3>Messaging recommendations</h3>
          <RecommendationList items={result.messaging_recommendations} emptyMessage="No messaging recommendations were returned." />
        </section>
        <section className="audience-guidance-card">
          <h3>Creative considerations</h3>
          <RecommendationList items={result.creative_considerations} emptyMessage="No creative considerations were returned." />
        </section>
      </div>

      <div className="audience-caveat-grid">
        <section className="audience-caveat-card">
          <h3>Assumptions</h3>
          <RecommendationList items={result.assumptions} emptyMessage="No additional assumptions listed." />
        </section>
        <section className="audience-caveat-card">
          <h3>Limitations</h3>
          <RecommendationList items={result.limitations} emptyMessage="No limitations listed." />
        </section>
        <section className="audience-caveat-card">
          <h3>Missing information</h3>
          <RecommendationList items={result.missing_information} emptyMessage="No additional information requested." />
        </section>
      </div>
    </div>
  );
};

export const AudienceAnalysisPanel = ({ campaignId }) => {
  const [analyses, setAnalyses] = useState([]);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState('');
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [analysisError, setAnalysisError] = useState('');
  const [historyReloadToken, setHistoryReloadToken] = useState(0);
  const requestInFlight = useRef(false);

  useEffect(() => {
    let active = true;
    const loadHistory = async () => {
      setIsLoadingHistory(true);
      setHistoryError('');
      try {
        const response = await campaignService.getAudienceAnalysisHistory(campaignId);
        const history = parseAudienceAnalysisHistory(response);
        if (active) {
          setAnalyses(history);
          setSelectedAnalysisId(history[0] ? String(history[0].id) : '');
        }
      } catch (error) {
        if (active) {
          const message = error instanceof Error && error.message.includes('response was incomplete')
            ? error.message
            : getApiErrorMessage(error, 'Unable to load audience-analysis history.');
          setHistoryError(message);
        }
      } finally {
        if (active) setIsLoadingHistory(false);
      }
    };

    loadHistory();
    return () => { active = false; };
  }, [campaignId, historyReloadToken]);

  const handleAnalyzeAudience = async () => {
    if (!campaignId || requestInFlight.current) return;
    requestInFlight.current = true;
    setIsAnalyzing(true);
    setAnalysisError('');
    try {
      const run = await campaignService.createAudienceAnalysis(campaignId);
      if (!isAudienceAnalysisRun(run)) {
        throw new Error('The audience-analysis response was incomplete or invalid. Please try again.');
      }
      setAnalyses((previous) => [run, ...previous.filter((item) => item.id !== run.id)]);
      setSelectedAnalysisId(String(run.id));
    } catch (error) {
      const message = error instanceof Error && error.message.includes('response was incomplete')
        ? error.message
        : getApiErrorMessage(error, 'Unable to analyze this audience. Please try again.');
      setAnalysisError(message);
    } finally {
      requestInFlight.current = false;
      setIsAnalyzing(false);
    }
  };

  const selectedRun = analyses.find((run) => String(run.id) === selectedAnalysisId) || null;
  const latestRun = analyses[0] || null;
  const isSelectedLatest = Boolean(selectedRun && latestRun && selectedRun.id === latestRun.id);

  return (
    <section className="audience-analysis-section" id="audience-analysis" aria-labelledby="audience-analysis-title">
      <div className="audience-analysis-header">
        <div>
          <p className="page-kicker">Campaign insights</p>
          <h2 id="audience-analysis-title">Audience Analysis</h2>
          <p>Explore possible audience segments and campaign-specific messaging ideas.</p>
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={handleAnalyzeAudience}
          disabled={isAnalyzing || !campaignId}
        >
          {isAnalyzing ? 'Analyzing audience…' : 'Analyze Audience'}
        </button>
      </div>

      <p className="audience-analysis-notice" role="note">{ANALYSIS_NOTICE}</p>

      {analysisError && <div className="alert alert-error" role="alert">{analysisError}</div>}
      {historyError && <div className="alert alert-error" role="alert">{historyError}</div>}

      {isLoadingHistory ? (
        <div className="audience-history-loading" role="status">
          <span className="auth-spinner" aria-hidden="true" />
          <span>Loading saved audience analyses…</span>
        </div>
      ) : historyError && analyses.length === 0 ? (
        <div className="audience-empty-state">
          <h3>Saved analyses unavailable</h3>
          <p>Retry loading this campaign’s audience-analysis history, or run a new analysis.</p>
          <button type="button" className="btn-secondary" onClick={() => setHistoryReloadToken((value) => value + 1)}>
            Retry loading history
          </button>
        </div>
      ) : analyses.length === 0 ? (
        <div className="audience-empty-state">
          <h3>No audience analysis yet</h3>
          <p>Run an analysis to see potential segments, targeting approaches, and messaging ideas for this campaign.</p>
        </div>
      ) : (
        <>
          <div className="audience-history-controls">
            <label htmlFor="audience-analysis-history">Saved analyses</label>
            <select
              id="audience-analysis-history"
              className="form-select"
              value={selectedAnalysisId}
              onChange={(event) => setSelectedAnalysisId(event.target.value)}
              aria-label="Choose a saved audience analysis"
            >
              {analyses.map((run, index) => (
                <option key={run.id} value={String(run.id)}>
                  {index === 0 ? 'Latest · ' : ''}{formatAudienceAnalysisDate(run.created_at)}
                </option>
              ))}
            </select>
            {selectedRun && <span className={isSelectedLatest ? 'audience-history-state is-latest' : 'audience-history-state'}>{isSelectedLatest ? 'Showing latest' : 'Showing earlier analysis'}</span>}
          </div>
          {selectedRun
            ? <AudienceAnalysisResultView run={selectedRun} isLatest={isSelectedLatest} />
            : <div className="alert alert-error" role="alert">The selected saved analysis is unavailable. Choose another run or analyze again.</div>}
        </>
      )}
    </section>
  );
};

export default AudienceAnalysisPanel;
